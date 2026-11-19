import pytest

from greeter.complimenter import FALLBACK_COMPLIMENT, FALLBACK_COMPLIMENTS, Complimenter, parse_command
from greeter.config import Settings
from greeter.voice import build_session_config


@pytest.mark.parametrize("text", [
    "Reachy, be quiet.", "be quiet please", "Shut up!", "Richie stop talking", "Quiet.", "hush", "keep quiet",
])
def test_quiet_commands(text):
    assert parse_command(text) == "quiet"


@pytest.mark.parametrize("text", ["Reachy, wake up!", "wake up", "Richie wake up."])
def test_wake_commands(text):
    assert parse_command(text) == "wake"


@pytest.mark.parametrize("text", ["It's quiet in here", "I love your antennas", "what's up", ""])
def test_ordinary_speech_is_not_a_command(text):
    assert parse_command(text) is None


class Speech:
    def __init__(self): self.lines = []
    async def put(self, text, max_age_s=None): self.lines.append(text)


class Moves:
    def __init__(self): self.calls = []
    async def perk_up(self): self.calls.append("perk_up")
    async def dance(self): self.calls.append("dance")
    async def sad(self): self.calls.append("sad")


def make(compliment="Love that green jacket!"):
    async def get(avoid=None): return compliment
    speech, moves = Speech(), Moves()
    return Complimenter(speech, moves, get), speech, moves


async def visit(c, start):
    for t in (start, start + 1.0, start + 2.0):
        await c.handle_face(True, t)
    await c.drain()


async def test_compliments_a_new_person_after_a_moment():
    c, speech, moves = make()
    await c.handle_face(True, 0.0)
    await c.drain()
    assert speech.lines == []
    await visit(c, 0.5)
    assert speech.lines == ["Love that green jacket!"] and moves.calls == ["perk_up"]


async def test_same_person_is_complimented_once_and_next_person_too():
    c, speech, _ = make()
    await visit(c, 0.0)
    await visit(c, 3.0)  # still the same person
    assert len(speech.lines) == 1
    await c.handle_face(False, 6.0)
    await visit(c, 10.0)  # nobody for 4 s, then someone new
    assert len(speech.lines) == 2


async def test_falls_back_when_vision_has_nothing():
    c, speech, _ = make(compliment=None)
    await visit(c, 0.0)
    assert speech.lines == [FALLBACK_COMPLIMENT]


async def test_quiet_until_woken():
    c, speech, _ = make()
    assert c.hear("Reachy, be quiet") == "quiet" and c.quiet
    await visit(c, 0.0)
    assert speech.lines == []
    assert c.hear("hello there") is None and c.quiet
    assert c.hear("be quiet") is None  # already quiet
    assert c.hear("Reachy wake up") == "wake" and not c.quiet
    await visit(c, 3.0)  # the person who arrived while he was quiet gets one now
    assert speech.lines == ["Love that green jacket!"]


async def test_queued_line_is_dropped_once_quiet():
    c, _, _ = make()
    said = []
    async def say(text): said.append(text)
    c.hear("shut up")
    await c.say("You look great!", say)
    assert said == []
    c.hear("wake up")
    await c.say("You look great!", say)
    assert said == ["You look great!"]


def test_quiet_session_transcribes_but_never_answers():
    s = Settings(openai_api_key="sk-x")
    vad = build_session_config(s, "x", [], auto_reply=False)["audio"]["input"]["turn_detection"]
    assert vad["create_response"] is False and vad["interrupt_response"] is False
    assert build_session_config(s, "x", [], auto_reply=False)["audio"]["input"]["transcription"]
    assert build_session_config(s, "x", [])["audio"]["input"]["turn_detection"]["create_response"] is True


async def test_someone_still_in_view_gets_a_fresh_compliment_every_15s():
    seen = []
    texts = iter(["Love the red scarf!", "Those white sneakers are crisp!"])
    async def get(avoid=None):
        seen.append(list(avoid)); return next(texts)
    speech = Speech()
    c = Complimenter(speech, Moves(), get)
    for t in range(0, 20):
        await c.handle_face(True, float(t))
        await c.drain()
    assert speech.lines == ["Love the red scarf!", "Those white sneakers are crisp!"]
    assert seen[1] == ["Love the red scarf!"]  # the vision model is told what not to repeat


async def test_fallbacks_rotate_and_repeats_are_replaced():
    c, speech, _ = make(compliment="Nice shirt!")
    await visit(c, 0.0)
    await c.handle_face(False, 3.0)
    await visit(c, 10.0)  # vision repeats itself: use a backup instead
    assert speech.lines == ["Nice shirt!", FALLBACK_COMPLIMENTS[0]]


@pytest.mark.parametrize("text", [
    "Reachy, do a dance!", "Richie do a dance", "Can you do a little dance?", "dance for us", "Ritchie, dance!",
    "show us your dance", "do another dance",
])
def test_dance_commands(text):
    assert parse_command(text) == "dance"


@pytest.mark.parametrize("text", ["I went dancing last night", "the dance floor is over there"])
def test_talking_about_dancing_is_not_a_command(text):
    assert parse_command(text) is None


async def test_dance_runs_once_and_works_while_quiet():
    c, speech, moves = make()
    c.hear("be quiet")
    assert c.hear("Reachy, do a dance") == "dance"
    assert c.hear("do a dance") is None  # already dancing
    await c.drain()
    assert moves.calls == ["dance"] and not c.dancing and speech.lines == []


async def test_voice_model_can_start_a_dance_but_never_two_at_once():
    c, _, moves = make()
    assert c.start_dance("tool") is True
    assert c.start_dance("tool") is False
    assert c.hear("do a dance") is None
    await c.drain()
    assert moves.calls == ["dance"]
    assert c.start_dance("tool") is True
    await c.drain()
    assert moves.calls == ["dance", "dance"]

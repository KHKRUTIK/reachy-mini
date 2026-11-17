import asyncio
from types import SimpleNamespace

from greeter.arrival import ArrivalPrompter
from greeter.checkin import CheckinGate
from greeter.greeter import Greeter
from greeter.robot import Moves, SEARCH_YAWS_DEG
from greeter.tools import TOOLS, make_tool_handler
from greeter.voice import RealtimeVoice


class FakeMini:
    def __init__(self):
        self.gotos = []
        self.media = SimpleNamespace(get_input_audio_samplerate=lambda: 16000, get_output_audio_samplerate=lambda: 16000)

    def goto_target(self, **kw):
        self.gotos.append(kw)


async def test_search_stops_when_face_found():
    mini = FakeMini()
    checks = iter([False, False, True])
    found = await Moves(mini, "http://127.0.0.1:9").search(lambda: next(checks))
    assert found is True
    assert len(mini.gotos) == 3  # stopped at the third look


async def test_search_gives_up_and_faces_forward():
    mini = FakeMini()
    found = await Moves(mini, "http://127.0.0.1:9").search(lambda: False)
    assert found is False
    assert len(mini.gotos) == len(SEARCH_YAWS_DEG) + 1
    assert mini.gotos[-1]["body_yaw"] == 0.0


class SearchMoves:
    def __init__(self, result=True): self.searches, self.result = 0, result
    async def search(self, found): self.searches += 1; return self.result
    async def welcome(self): pass


class NullSpeech:
    async def put(self, text, max_age_s=None): pass


def make(moves):
    async def none(): return None
    return Greeter(NullSpeech(), moves, CheckinGate(), ArrivalPrompter(), none)


async def test_find_person_searches():
    moves = SearchMoves()
    g = make(moves)
    assert await g.find_person(lambda: False, now=0.0) is True
    assert moves.searches == 1


async def test_auto_search_has_cooldown_but_asked_search_does_not():
    moves = SearchMoves(result=False)
    g = make(moves)
    await g.find_person(lambda: False, now=0.0, auto=True)
    await g.find_person(lambda: False, now=5.0, auto=True)      # too soon: skipped
    assert moves.searches == 1
    await g.find_person(lambda: False, now=6.0)                  # guest asked: always look
    assert moves.searches == 2
    await g.find_person(lambda: False, now=30.0, auto=True)
    assert moves.searches == 3


def test_look_at_me_tool_exists():
    assert "look_at_me" in [t["name"] for t in TOOLS]


async def test_handler_routes_look_at_me():
    async def rate(): return {}
    async def sad(): pass
    async def look(): return True
    handle = make_tool_handler(rate, sad, look)
    out = await handle("look_at_me", {})
    assert out["found"] is True and "say" in out


class FakeConn:
    def __init__(self, events): self._events = events
    def __aiter__(self): return self._gen()
    async def _gen(self):
        for e in self._events:
            yield e


async def test_voice_reports_guest_speech():
    mini = FakeMini()
    mini.media.start_playing = lambda: None
    mini.media.audio = SimpleNamespace(clear_player=lambda: None)
    voice = RealtimeVoice(SimpleNamespace(voice="marin"), mini, "x")
    heard = []
    voice.on_guest_speech = lambda: heard.append(1)
    voice._conn = FakeConn([SimpleNamespace(type="input_audio_buffer.speech_started")])
    await voice._event_loop()
    assert heard == [1]


async def test_auto_search_waits_while_a_face_was_just_seen():
    # A guest holding their phone up hides their face; don't spin away from the QR code.
    moves = SearchMoves(result=False)
    g = make(moves)
    await g.handle_face(True, now=100.0)
    await g.find_person(lambda: False, now=104.0, auto=True)
    assert moves.searches == 0
    await g.find_person(lambda: False, now=100.0 + 8.1, auto=True)
    assert moves.searches == 1


async def test_auto_search_waits_after_a_scan():
    from greeter.checkin import ScanResult
    moves = SearchMoves(result=False)
    g = make(moves)
    await g.handle_scan(ScanResult("success", "Ada Lovelace", 200.0))
    await g.drain()
    await g.find_person(lambda: False, now=210.0, auto=True)
    assert moves.searches == 0
    await g.find_person(lambda: False, now=215.1, auto=True)
    assert moves.searches == 1


async def test_asked_search_ignores_recent_face_and_scan():
    moves = SearchMoves(result=False)
    g = make(moves)
    await g.handle_face(True, now=100.0)
    await g.find_person(lambda: False, now=101.0)
    assert moves.searches == 1


def _yaws(mini):
    import numpy as np
    return [round(float(np.rad2deg(g["body_yaw"]))) for g in mini.gotos]


async def test_turn_to_sweeps_until_it_finds_a_face_and_remembers_the_spot():
    mini = FakeMini()
    looks = iter([False, False, True])
    moves = Moves(mini, "http://127.0.0.1:9", sees_face=lambda: next(looks))
    await moves.turn_to("left")
    assert _yaws(mini) == [30, 50, 70]          # stopped where it found someone
    mini.gotos.clear()
    moves._side = "right"                        # pretend he's facing the other person
    moves.sees_face = lambda: True
    await moves.turn_to("left")
    assert _yaws(mini) == [70]                   # straight back to where they were


async def test_turn_to_resweeps_if_the_person_moved():
    mini = FakeMini()
    moves = Moves(mini, "http://127.0.0.1:9", sees_face=lambda: True)
    moves._spots["right"] = -70.0
    looks = iter([False, False, True])           # not at the old spot; found again at -50
    moves.sees_face = lambda: next(looks)
    await moves.turn_to("right")
    assert _yaws(mini) == [-70, -30, -50]
    assert moves._spots["right"] == -50.0


async def test_turn_to_gives_up_at_a_default_angle_and_keeps_looking_next_time():
    mini = FakeMini()
    moves = Moves(mini, "http://127.0.0.1:9", sees_face=lambda: False)
    await moves.turn_to("right")
    assert _yaws(mini) == [-30, -50, -70, -85, -60]
    assert "right" not in moves._spots
    moves.forget_sides()
    assert moves._side is None


async def test_turn_to_rotates_body_once_per_side():
    mini = FakeMini()
    moves = Moves(mini, "http://127.0.0.1:9")
    await moves.turn_to("left")
    await moves.turn_to("left")   # already there: no move
    assert len(mini.gotos) == 1 and mini.gotos[0]["body_yaw"] > 0  # positive yaw = his left
    await moves.turn_to("right")
    assert len(mini.gotos) == 2 and mini.gotos[1]["body_yaw"] < 0

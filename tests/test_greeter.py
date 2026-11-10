import asyncio

from greeter.arrival import ArrivalPrompter
from greeter.checkin import CheckinGate, ScanResult as R
from greeter.greeter import Greeter
from greeter.lines import FRONT_DESK_LINE, QR_PROMPT_LINE, WRONG_CODE_LINE


class FakeSpeech:
    def __init__(self): self.lines = []
    async def put(self, text, max_age_s=None): self.lines.append(text)


class FakeMoves:
    def __init__(self): self.calls = []
    async def welcome(self): self.calls.append("welcome")
    async def front_desk(self): self.calls.append("front_desk")
    async def perk_up(self): self.calls.append("perk_up")


def make(compliment=None, delay=0.0):
    speech, moves = FakeSpeech(), FakeMoves()
    async def get_compliment():
        await asyncio.sleep(delay)
        return compliment
    g = Greeter(speech, moves, CheckinGate(), ArrivalPrompter(), get_compliment, compliment_window_s=0.2)
    return g, speech, moves


async def test_success_welcomes_by_first_name():
    g, speech, moves = make()
    await g.handle_scan(R("success", "Sarah Chen", 0))
    await g.drain()
    assert speech.lines == ["Welcome, Sarah! MLAI welcomes you to the OpenAI Dev Day!"]
    assert moves.calls == ["welcome"]


async def test_compliment_follows_welcome_when_quick():
    g, speech, _ = make(compliment="Love your shirt!")
    await g.handle_scan(R("success", "Sam", 0))
    await g.drain()
    assert speech.lines == ["Welcome, Sam! MLAI welcomes you to the OpenAI Dev Day!", "Love your shirt!"]


async def test_slow_compliment_is_dropped():
    g, speech, _ = make(compliment="Love your shirt!", delay=0.5)
    await g.handle_scan(R("success", "Sam", 0))
    await g.drain()
    assert speech.lines == ["Welcome, Sam! MLAI welcomes you to the OpenAI Dev Day!"]


async def test_failure_sends_to_front_desk():
    g, speech, moves = make()
    await g.handle_scan(R("failure", None, 0))
    await g.drain()
    assert speech.lines == [FRONT_DESK_LINE] and moves.calls == ["front_desk"]


async def test_wrong_code_coaches():
    g, speech, _ = make()
    await g.handle_scan(R("wrong_code", None, 0))
    assert speech.lines == [WRONG_CODE_LINE]


async def test_already_checked_in_after_welcome_is_silent():
    g, speech, _ = make()
    await g.handle_scan(R("success", "Sam", 0))
    await g.handle_scan(R("failure", "Sam", 5))
    await g.drain()
    assert speech.lines == ["Welcome, Sam! MLAI welcomes you to the OpenAI Dev Day!"]


async def test_face_dwell_prompts_for_qr():
    g, speech, moves = make()
    for t in range(6):
        await g.handle_face(True, float(t))
    await g.drain()
    assert speech.lines == [QR_PROMPT_LINE] and moves.calls == ["perk_up"]


async def test_scan_during_visit_prevents_qr_prompt():
    g, speech, _ = make()
    await g.handle_face(True, 0.0)
    await g.handle_scan(R("success", "Sam", 1.0))
    for t in range(2, 8):
        await g.handle_face(True, float(t))
    assert QR_PROMPT_LINE not in speech.lines


async def test_face_updates_ignored_while_moving():
    g, speech, _ = make()
    await g.handle_face(True, 0.0)
    await g.handle_scan(R("success", "Sam", 0.5))
    g.moving = True
    await g.handle_face(False, 1.0)   # head busy: tracking paused, must not end the visit
    g.moving = False
    for t in range(3, 12):
        await g.handle_face(True, float(t))
    assert QR_PROMPT_LINE not in speech.lines


async def test_already_checked_in_says_welcome_back():
    g, speech, moves = make(compliment="Nice hat!")
    await g.handle_scan(R("already", "Alan Philip", 0))
    await g.drain()
    assert speech.lines == ["Welcome back, Alan! You've already checked in, so take a seat whenever you're ready."]
    assert moves.calls == ["welcome"]


async def test_no_qr_prompt_while_conversation_active():
    g, speech, _ = make()
    g.conversation_active = lambda: True
    for t in range(8):
        await g.handle_face(True, float(t))
    assert speech.lines == []
    g.conversation_active = lambda: False
    await g.handle_face(True, 8.0)
    await g.drain()
    assert speech.lines == [QR_PROMPT_LINE]


async def test_express_off_warning_is_spoken_once_per_minute():
    from greeter.lines import EXPRESS_OFF_LINE
    g, speech, _ = make()
    await g.handle_scan(R("express_off", None, 0))
    await g.handle_scan(R("express_off", None, 30))
    await g.handle_scan(R("express_off", None, 61))
    assert speech.lines == [EXPRESS_OFF_LINE, EXPRESS_OFF_LINE]


async def test_deliberate_rescan_says_all_set():
    g, speech, _ = make()
    await g.handle_scan(R("success", "Luis Saso", 0))
    await g.handle_scan(R("already", "Luis Saso", 5))
    await g.handle_scan(R("already", "Luis Saso", 15))
    await g.handle_scan(R("already", "Luis Saso", 25))
    await g.drain()
    assert speech.lines == [
        "Welcome, Luis! MLAI welcomes you to the OpenAI Dev Day!",
        "You're all checked in, Luis! Take a seat whenever you're ready.",
    ]


async def test_compliment_dropped_if_another_welcome_came_after():
    g, speech, _ = make(compliment="Love your shirt!", delay=0.05)
    await g.handle_scan(R("success", "Alice", 0))
    await g.handle_scan(R("success", "Ben", 0.5))
    await g.drain()
    # Alice's compliment would land after Ben's welcome -> dropped; only Ben's own remains.
    assert speech.lines == [
        "Welcome, Alice! MLAI welcomes you to the OpenAI Dev Day!",
        "Welcome, Ben! MLAI welcomes you to the OpenAI Dev Day!",
        "Love your shirt!",
    ]


async def test_moves_never_overlap():
    g, _, _ = make()
    active, peak = 0, 0
    async def slow_move():
        nonlocal active, peak
        active += 1; peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
    g._moves.welcome = slow_move
    await g.handle_scan(R("success", "Alice", 0))
    await g.handle_scan(R("success", "Ben", 0.5))
    await g.drain()
    assert peak == 1


async def test_welcome_lines_carry_a_max_age():
    class AgeSpeech(FakeSpeech):
        async def put(self, text, max_age_s=None):
            self.lines.append((text, max_age_s))
    g, _, _ = make()
    g._speech = AgeSpeech()
    await g.handle_scan(R("success", "Sam", 0))
    await g.drain()
    assert g._speech.lines[0][1] == 10.0

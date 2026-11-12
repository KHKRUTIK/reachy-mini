import asyncio

import cv2
import numpy as np
from reachy_mini.vision.face_detector import Face

from greeter.arrival import ArrivalPrompter
from greeter.checkin import CheckinGate
from greeter.greeter import Greeter
from greeter.tools import TOOLS, make_tool_handler, rate_fit

FRAME = np.zeros((720, 1280, 3), np.uint8)


def face(x, y, w, h):
    return Face(bbox=(x, y, w, h), right_eye=(0, 0), left_eye=(0, 0), nose=(0, 0))


GUEST = face(600, 100, 100, 120)


async def _rate_ok(jpeg):
    return "9/10, that print is doing a lot of work"


def test_tools_are_rate_look_and_sad():
    assert [t["name"] for t in TOOLS] == ["rate_outfit", "look_at_me", "act_sad"]
    assert all(t["type"] == "function" for t in TOOLS)


async def test_rate_fit_returns_rating():
    out = await rate_fit(lambda: FRAME, lambda f: [GUEST], _rate_ok)
    assert out == {"rating": "9/10, that print is doing a lot of work"}


async def test_rate_fit_without_frame_asks_to_step_back():
    out = await rate_fit(lambda: None, lambda f: [GUEST], _rate_ok)
    assert "rating" not in out and "step back" in out["say"]


async def test_rate_fit_with_no_face_asks_to_step_in_front():
    out = await rate_fit(lambda: FRAME, lambda f: [], _rate_ok)
    assert "rating" not in out and "in front" in out["say"]


async def test_rate_fit_with_two_people_rates_the_main_one():
    out = await rate_fit(lambda: FRAME, lambda f: [GUEST, face(100, 100, 90, 110)], _rate_ok)
    assert out["rating"].startswith("9/10")


async def test_rate_fit_blacks_out_a_face_behind_the_guest():
    frame = np.full((720, 1280, 3), 255, np.uint8)
    behind = face(620, 300, 60, 70)  # smaller face inside the guest's outfit area
    sent = []
    async def rate(jpeg):
        sent.append(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)); return "8/10"
    out = await rate_fit(lambda: frame, lambda f: [GUEST, behind], rate)
    assert out == {"rating": "8/10"}
    # crop starts at y=238 and x=500; the masked face sits at rows 300-370, cols 620-680
    assert sent[0][300 - 238 + 10, 620 - 500 + 10].max() < 40
    assert frame.min() == 255  # original frame untouched


async def test_rate_fit_when_outfit_out_of_view_asks_to_step_back():
    out = await rate_fit(lambda: FRAME, lambda f: [face(600, 500, 100, 150)], _rate_ok)  # chin near bottom
    assert "rating" not in out and "step back" in out["say"]


async def test_rate_fit_when_model_has_nothing():
    async def rate_none(jpeg):
        return None
    out = await rate_fit(lambda: FRAME, lambda f: [GUEST], rate_none)
    assert "rating" not in out and "say" in out


async def test_handler_routes_tools():
    calls = []
    async def rate():
        calls.append("rate"); return {"rating": "8/10"}
    async def sad():
        calls.append("sad")
    handle = make_tool_handler(rate, sad)
    rated = await handle("rate_outfit", {})
    assert rated["rating"] == "8/10" and "say" in rated
    sad_out = await handle("act_sad", {})
    assert sad_out["ok"] is True
    assert "error" in await handle("nope", {})
    await asyncio.sleep(0)
    assert calls == ["rate", "sad"]


class FakeMoves:
    def __init__(self): self.calls = []
    async def sad(self): self.calls.append("sad")


class NullSpeech:
    async def put(self, text, max_age_s=None): pass


async def test_greeter_act_sad_runs_sad_move():
    moves = FakeMoves()
    async def no_compliment(): return None
    g = Greeter(NullSpeech(), moves, CheckinGate(), ArrivalPrompter(), no_compliment)
    await g.act_sad()
    await g.drain()
    assert moves.calls == ["sad"]

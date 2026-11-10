import asyncio
from types import SimpleNamespace

import numpy as np
from reachy_mini.vision.face_detector import Face

from greeter.compliment import crop_below_face, suggest_compliment

FRAME = np.zeros((720, 1280, 3), np.uint8)


def face(x, y, w, h):
    return Face(bbox=(x, y, w, h), right_eye=(0, 0), left_eye=(0, 0), nose=(0, 0))


def test_crop_returns_none_without_face():
    assert crop_below_face(FRAME, []) is None


def test_crop_starts_below_chin():
    crop = crop_below_face(FRAME, [face(600, 100, 100, 120)])
    assert crop is not None and crop.shape[0] == 720 - int(100 + 120 + 0.15 * 120)


def test_crop_width_is_three_face_widths_clamped():
    crop = crop_below_face(FRAME, [face(600, 100, 100, 120)])
    assert crop.shape[1] == 300  # centre 650 ± 150
    edge = crop_below_face(FRAME, [face(0, 100, 100, 120)])
    assert edge.shape[1] == 200  # clamped at the left edge: 0..200


def test_crop_uses_largest_face():
    crop = crop_below_face(FRAME, [face(100, 50, 40, 40), face(600, 100, 100, 120)])
    assert crop.shape[0] == 720 - int(100 + 120 + 0.15 * 120)


def test_crop_too_short_returns_none():
    assert crop_below_face(FRAME, [face(600, 500, 100, 150)]) is None  # chin near the bottom


class FakeClient:
    def __init__(self, text=None, delay=0.0, error=None):
        async def create(**kwargs):
            self.kwargs = kwargs
            await asyncio.sleep(delay)
            if error:
                raise error
            return SimpleNamespace(output_text=text)
        self.responses = SimpleNamespace(create=create)


async def test_suggest_returns_compliment():
    c = FakeClient("Love the Japanese design on your shirt!")
    assert await suggest_compliment(c, "m", b"jpg") == "Love the Japanese design on your shirt!"
    content = c.kwargs["input"][0]["content"]
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")


async def test_suggest_returns_none_for_NONE():
    assert await suggest_compliment(FakeClient(" NONE. "), "m", b"jpg") is None


async def test_suggest_returns_none_for_empty():
    assert await suggest_compliment(FakeClient(""), "m", b"jpg") is None


async def test_suggest_returns_none_on_timeout():
    assert await suggest_compliment(FakeClient("Nice!", delay=10), "m", b"jpg", timeout_s=0.1) is None


async def test_suggest_returns_none_on_error():
    assert await suggest_compliment(FakeClient(error=RuntimeError("api down")), "m", b"jpg") is None

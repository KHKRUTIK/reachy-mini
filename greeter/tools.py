"""Realtime voice tools: rate a guest's outfit on request, and act sad when someone is mean."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import cv2
import numpy as np

from greeter.compliment import crop_below_face

log = logging.getLogger(__name__)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "rate_outfit",
        "description": (
            "Look through your camera at the guest in front of you and rate their outfit out of 10. "
            "Call this only when the guest asks you to rate their fit, outfit, or look."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "act_sad",
        "description": (
            "Physically act sad: droop your head and antennas. Call this when someone is mean or rude "
            "to you, or says something that would make you sad."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]

STEP_BACK = "Ask them, playfully, to take a step back so you can see their whole outfit, then ask again."
STEP_IN_FRONT = "You can't see anyone. Ask them to stand right in front of you, then ask again."
ONE_AT_A_TIME = "You can see more than one person. Ask them to come up one at a time for a rating."
CANT_TELL = "You couldn't get a good look. Say so cheerfully and suggest trying again in a moment."


async def rate_fit(
    get_frame: Callable[[], np.ndarray | None],
    detect: Callable[[np.ndarray], list],
    rate: Callable[[bytes], Awaitable[str | None]],
) -> dict[str, str]:
    """Return {"rating": text} or {"say": guidance for the voice model}. The face never leaves the laptop."""
    frame = get_frame()
    if frame is None:
        return {"say": STEP_BACK}
    faces = detect(frame)
    if not faces:
        return {"say": STEP_IN_FRONT}
    if len(faces) > 1:
        return {"say": ONE_AT_A_TIME}
    crop = crop_below_face(frame, faces)
    if crop is None:
        return {"say": STEP_BACK}
    ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
    text = await rate(jpeg.tobytes()) if ok else None
    if not text:
        return {"say": CANT_TELL}
    return {"rating": text}


def make_tool_handler(
    rate_outfit: Callable[[], Awaitable[dict]],
    act_sad: Callable[[], Awaitable[None]],
) -> Callable[[str, dict], Awaitable[dict]]:
    async def handle(name: str, args: dict) -> dict:
        if name == "rate_outfit":
            out = await rate_outfit()
            if "rating" in out:
                out["say"] = "Tell them this rating in your own bright words, keeping the score and the detail."
            return out
        if name == "act_sad":
            await act_sad()
            return {
                "ok": True,
                "say": "You're drooping sadly. Say one short, gentle, slightly sad line, then bounce back kindly.",
            }
        return {"error": f"unknown tool {name}"}

    return handle

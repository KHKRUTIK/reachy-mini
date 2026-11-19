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
        "name": "look_at_me",
        "description": (
            "Turn around to find the person talking to you and face them. Call this when someone asks "
            "you to look at them, turn to them, or find them, or asks if you can see them."
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
    # Rate the main (largest, i.e. closest) person. Anyone else in view gets blacked out first,
    # so their face can't end up in the crop that goes to the vision model.
    main = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
    if len(faces) > 1:
        frame = _mask_faces(frame, [f for f in faces if f is not main])
    crop = crop_below_face(frame, [main])
    if crop is None:
        return {"say": STEP_BACK}
    ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
    text = await rate(jpeg.tobytes()) if ok else None
    if not text:
        return {"say": CANT_TELL}
    return {"rating": text}


def _mask_faces(frame: np.ndarray, faces: list) -> np.ndarray:
    """Copy of the frame with each face (plus a generous margin) painted black."""
    out = frame.copy()
    height, width = out.shape[:2]
    for f in faces:
        x, y, w, h = (int(round(float(v))) for v in f.bbox)  # the detector can return floats
        mx, my = int(0.3 * w), int(0.3 * h)
        out[max(0, y - my):min(height, y + h + my), max(0, x - mx):min(width, x + w + mx)] = 0
    return out


def make_tool_handler(
    rate_outfit: Callable[[], Awaitable[dict]],
    act_sad: Callable[[], Awaitable[None]],
    look_at_me: Callable[[], Awaitable[bool]] | None = None,
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
        if name == "look_at_me" and look_at_me:
            found = await look_at_me()
            return {
                "found": found,
                "say": "You found them and are now facing them; say so playfully." if found
                else "You looked around but couldn't spot them. Ask them to step in front of your camera.",
            }
        return {"error": f"unknown tool {name}"}

    return handle

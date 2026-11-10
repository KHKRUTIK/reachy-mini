"""Face-free clothing crop and an optional one-line compliment from a vision model."""
from __future__ import annotations

import asyncio
import base64
import logging

import numpy as np

log = logging.getLogger(__name__)

PROMPT = (
    "This photo shows a person's outfit from the shoulders down. Find something nice to say about "
    "their clothing or accessories: a colour, a design or print, a logo or slogan, the style, a "
    "jacket, a bag, a lanyard. Reply with ONE short, warm, specific compliment of at most 12 words, "
    "addressed to them as 'you'. Never mention body, face, age, weight, or anything personal. "
    "Only if the image shows no clothing at all (blank, too dark, or no person), reply exactly NONE."
)

MIN_CROP_HEIGHT = 80


def crop_below_face(frame: np.ndarray, faces: list) -> np.ndarray | None:
    """Return the region below the largest face's chin, or None (never a crop that could include a face)."""
    if not faces:
        return None
    x, y, w, h = max(faces, key=lambda f: f.bbox[2] * f.bbox[3]).bbox
    height, width = frame.shape[:2]
    top = int(y + h + 0.15 * h)
    cx = x + w / 2
    left, right = max(0, int(cx - 1.5 * w)), min(width, int(cx + 1.5 * w))
    if height - top < MIN_CROP_HEIGHT or right <= left:
        return None
    return frame[top:height, left:right]


async def suggest_compliment(client, model: str, crop_jpeg: bytes, timeout_s: float = 4.0) -> str | None:
    data_url = "data:image/jpeg;base64," + base64.b64encode(crop_jpeg).decode("ascii")
    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": PROMPT},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }],
                max_output_tokens=60,
            ),
            timeout=timeout_s,
        )
    except Exception as e:  # timeout, network, API errors: no compliment is fine
        log.info("compliment skipped: %s", e)
        return None
    text = (getattr(response, "output_text", None) or "").strip()
    if not text or text.strip(" .!").upper() == "NONE":
        log.info("compliment: model found nothing to say")
        return None
    log.info("compliment: %s", text)
    return text

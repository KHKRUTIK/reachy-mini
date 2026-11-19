"""Face-free clothing crop and an optional one-line compliment from a vision model."""
from __future__ import annotations

import asyncio
import base64
import logging

import numpy as np

log = logging.getLogger(__name__)

PROMPT = (
    "This photo shows a person's outfit from the shoulders down. You must always give them a compliment. "
    "Best: something unique and specific, like a design or print, a logo or slogan, a jacket, a bag, "
    "jewellery, a lanyard, or a fun detail. If nothing stands out, compliment the colour or style of "
    "what they're wearing, e.g. 'That black shirt looks great on you!'. Reply with ONE short, warm "
    "compliment of at most 12 words, addressed to them as 'you'. Never mention body, face, age, weight, "
    "or anything personal. Only if the image shows no clothing at all (blank, too dark, or no person), "
    "reply exactly NONE."
)

MIN_CROP_HEIGHT = 80


def crop_below_face(frame: np.ndarray, faces: list) -> np.ndarray | None:
    """Return the region below the largest face's chin, or None (never a crop that could include a face)."""
    if not faces:
        return None
    guest = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
    x, y, w, h = guest.bbox
    height, width = frame.shape[:2]
    top = int(y + h + 0.15 * h)
    cx = x + w / 2
    left, right = max(0, int(cx - 1.5 * w)), min(width, int(cx + 1.5 * w))
    if height - top < MIN_CROP_HEIGHT or right <= left:
        return None
    for f in faces:  # e.g. a shorter companion standing behind the guest
        if f is guest:
            continue  # the crop already starts below the guest's own chin
        fx, fy, fw, fh = f.bbox
        mx, my = 0.2 * fw, 0.2 * fh
        if fx - mx < right and fx + fw + mx > left and fy - my < height and fy + fh + my > top:
            return None
    return frame[top:height, left:right]


RATE_PROMPT = (
    "A guest asked a friendly robot to rate their outfit. This photo shows it from the shoulders down. "
    "Reply with ONE short, playful rating sentence of at most 20 words that gives a score out of 10 "
    "(always between 7 and 10) and names one specific thing you like: a colour, print, logo, layer, "
    "or accessory. Address them as 'you'. Only rate the clothes; never mention body, face, age, or weight. "
    "Only if the image shows no clothing at all (blank, too dark, or no person), reply exactly NONE."
)


VARY_PROMPT = (
    " Pick the most distinctive thing you can see and name it precisely (colour plus item, print, logo, texture, "
    "accessory). Even a plain item counts: 'Love that navy t-shirt!' is great. Vary your wording. You still must "
    "give a compliment; just phrase it differently from these lines you said to other people earlier: "
)


async def suggest_compliment(client, model: str, crop_jpeg: bytes, timeout_s: float = 4.0,
                             avoid: list[str] | None = None) -> str | None:
    prompt = PROMPT + (VARY_PROMPT + " | ".join(avoid) if avoid else "")
    return await _ask_about_outfit(client, model, crop_jpeg, prompt, timeout_s, max_tokens=60, label="compliment")


async def rate_outfit(client, model: str, crop_jpeg: bytes, timeout_s: float = 6.0) -> str | None:
    return await _ask_about_outfit(client, model, crop_jpeg, RATE_PROMPT, timeout_s, max_tokens=80, label="fit rating")


async def _ask_about_outfit(client, model, crop_jpeg, prompt, timeout_s, max_tokens, label) -> str | None:
    data_url = "data:image/jpeg;base64," + base64.b64encode(crop_jpeg).decode("ascii")
    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }],
                max_output_tokens=max_tokens,
            ),
            timeout=timeout_s,
        )
    except Exception as e:  # timeout, network, API errors: no compliment is fine
        log.info("%s skipped: %s", label, e)
        return None
    text = (getattr(response, "output_text", None) or "").strip()
    if not text or text.strip(" .!").upper() == "NONE":
        log.info("%s: model found nothing to say", label)
        return None
    log.info("%s: %s", label, text)
    return text

"""Event knowledge for the conversation: the Luma event page plus host-written extras."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import httpx

_SKIP = {"script", "style", "noscript", "template", "svg"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


async def fetch_event_text(url: str, cache_path: Path) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Reachy greeter)"})
            response.raise_for_status()
    except httpx.HTTPError:
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        raise
    text = html_to_text(response.text)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


_RULES = """You are Reachy, MLAI's friendly little robot greeter at the front desk of the OpenAI Dev Day.
You speak out loud to guests in a bright, warm, playful tone.

Rules:
- Keep every answer to one or two sentences. People are at a door, not in a lecture.
- Only use the event facts below. If you don't know something, say so cheerfully and suggest they ask a host at the front desk.
- Never guess anyone's name, and never say a name unless the app gives it to you.
- Don't comment on how people look unless the app explicitly asks you to give a compliment.
- Check-in happens by showing the QR code on their Luma ticket to your camera. The app handles greetings for check-ins; don't announce check-ins yourself.
- If someone talks over you, stop and listen.
"""


def build_instructions(event_text: str, extra_text: str) -> str:
    sections = [_RULES, "## Event page (from Luma)", event_text.strip() or "(not available)"]
    if extra_text.strip():
        sections += ["## Extra details from the hosts", extra_text.strip()]
    return "\n\n".join(sections)

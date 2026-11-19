"""Compliment mode: Reachy compliments everyone who walks up, and goes quiet on command until woken."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from typing import Any, Awaitable, Callable

from greeter.arrival import ArrivalPrompter

log = logging.getLogger(__name__)

# Used (in turn) when the camera can't see enough clothing; the vision model's line is always preferred.
FALLBACK_COMPLIMENTS = [
    "You're looking great today!",
    "Ooh, love the whole look you've got going on!",
    "Now that's a great outfit choice!",
    "You've got serious style, I can tell!",
    "Looking sharp! Great energy, too.",
    "Wow, you're bringing the style today!",
    "Love your vibe! You look fantastic.",
    "That look really suits you!",
]
FALLBACK_COMPLIMENT = FALLBACK_COMPLIMENTS[0]
REPEAT_AFTER_S = 15.0  # someone (or a crowd) still in view: another, different compliment this often
RECENT_KEPT = 10
WAKE_LINE = "I'm awake! Who's looking fabulous today?"
LINE_MAX_AGE_S = 10.0  # never compliment someone who has likely walked off

_QUIET = re.compile(
    r"\b(?:(?:be|keep|stay|go|get) quiet|quiet (?:down|please)|shut up|stop talking|hush|shush|go to sleep)\b"
)
_WAKE = re.compile(r"\bwake up\b")
_DANCE = re.compile(
    r"\b(?:do|show|give|bust|let's see|lets see) (?:us |me )?(?:a |the |your |some |another |one more |a little )?"
    r"(?:little )?(?:dance|dancing|jig|boogie)\b|\bdance for (?:us|me)\b|\b(?:reachy|richie|ritchie),? dance\b"
)


def parse_command(transcript: str) -> str | None:
    """'quiet', 'wake', 'dance' or None, from what someone just said."""
    text = re.sub(r"[^\w\s']", " ", transcript.lower())
    text = re.sub(r"\s+", " ", text).strip()
    if _WAKE.search(text):
        return "wake"
    if _DANCE.search(text):
        return "dance"
    if _QUIET.search(text) or text in ("quiet", "silence", "reachy quiet", "quiet reachy"):
        return "quiet"
    return None


INSTRUCTIONS = """You are Reachy, a small, cheerful robot at an event whose job is to make people feel good.
You speak out loud in a bright, warm, playful tone. The app compliments each new person who walks up; you don't need to.

About you (only if asked): you're a Reachy Mini Lite, an open-source desktop robot made by Pollen Robotics, now part of Hugging Face. Your voice runs on OpenAI's realtime voice model.

Rules:
- Always speak English, even if what you heard sounded like another language (it's probably background noise).
- Keep every answer to one or two short sentences.
- Only compliment clothes, style and energy. Never comment on body, face, age or weight.
- If someone asks you to rate their fit, outfit or look, call rate_outfit and follow what it returns.
- If someone is mean or rude to you, call act_sad, say one short, gentle line, then bounce back kindly.
- If someone tells you to be quiet, say nothing at all.
- If someone asks you to dance, say one short, excited line like "Ooh, watch this!" The app makes you dance; never say you can't.
- If someone talks over you, stop and listen.
"""


class Complimenter:
    """Compliments each new visit (a face that appears after a gap), unless he's been told to be quiet."""

    def __init__(
        self,
        speech: Any,
        moves: Any,
        get_compliment: Callable[[], Awaitable[str | None]],
        arrival: ArrivalPrompter | None = None,
        compliment_window_s: float = 6.0,
    ) -> None:
        self.speech = speech
        self._moves = moves
        self._get_compliment = get_compliment
        # New person = face after >3 s with nobody; compliment after 1 s in view; at most one every 4 s.
        self._arrival = arrival or ArrivalPrompter(dwell_s=1.0, cooldown_s=4.0, flicker_s=3.0, scan_block_s=0.0)
        self._window_s = compliment_window_s
        self.quiet = False
        self.recent: deque[str] = deque(maxlen=RECENT_KEPT)
        self._fallback_i = 0
        self._last_at = float("-inf")
        self._busy = False
        self.dancing = False
        self._tasks: set[asyncio.Task] = set()
        self._move_lock = asyncio.Lock()

    async def handle_face(self, present: bool, now: float, can_prompt: bool = True) -> None:
        allowed = can_prompt and not self.quiet and not self._busy and not self.dancing
        new_person = self._arrival.update(present, now, can_prompt=allowed)
        # Repeats only once someone has had their first one (the arrival rule handles the first, after a pause).
        still_here = present and allowed and self._last_at > float("-inf") and now - self._last_at >= REPEAT_AFTER_S
        if new_person or still_here:
            self._last_at = now
            self._busy = True
            self._spawn(self._compliment())

    def hear(self, transcript: str) -> str | None:
        """Act on 'be quiet' / 'wake up'. Returns the command if it changed his state."""
        command = parse_command(transcript)
        if command == "quiet" and not self.quiet:
            self.quiet = True
            log.info("quiet mode ON (heard %r)", transcript)
            return command
        if command == "wake" and self.quiet:
            self.quiet = False
            log.info("quiet mode OFF (heard %r)", transcript)
            return command
        if command == "dance" and not self.dancing:  # dancing is silent, so it works in quiet mode too
            log.info("dance requested (heard %r)", transcript)
            self.dancing = True
            self._spawn(self._dance())
            return command
        return None

    async def _dance(self) -> None:
        try:
            await self._move(self._moves.dance)
        finally:
            self.dancing = False

    async def say(self, text: str, say: Callable[[str], Awaitable[None]]) -> None:
        """Speech-queue sink: a line queued before 'be quiet' is dropped, not spoken."""
        if self.quiet:
            log.info("quiet: dropped %r", text)
            return
        await say(text)

    async def act_sad(self) -> None:
        self._spawn(self._move(self._moves.sad))

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _compliment(self) -> None:
        try:
            try:
                text = await asyncio.wait_for(self._get_compliment(list(self.recent)), self._window_s)
            except asyncio.TimeoutError:
                log.info("compliment too slow; using a generic one")
                text = None
            if self.quiet:
                return
            if not text or text in self.recent:
                text = self._next_fallback()
            self.recent.append(text)
            await self.speech.put(text, max_age_s=LINE_MAX_AGE_S)
            self._spawn(self._move(self._moves.perk_up))
        finally:
            self._busy = False

    def _next_fallback(self) -> str:
        text = FALLBACK_COMPLIMENTS[self._fallback_i % len(FALLBACK_COMPLIMENTS)]
        self._fallback_i += 1
        return text

    async def _move(self, fn: Callable[[], Awaitable[None]]) -> None:
        async with self._move_lock:
            try:
                await fn()
            except Exception:
                log.exception("move failed")

    def _spawn(self, coro: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

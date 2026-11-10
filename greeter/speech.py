"""Strictly ordered, one-at-a-time speech. Lines can expire so a backlog never plays late."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


class SpeechQueue:
    def __init__(self, say: Callable[[str], Awaitable[None]]) -> None:
        self._say = say
        self._queue: asyncio.Queue[tuple[str, float, float | None]] = asyncio.Queue()

    async def put(self, text: str, max_age_s: float | None = None) -> None:
        await self._queue.put((text, time.monotonic(), max_age_s))

    async def run(self) -> None:
        while True:
            text, queued_at, max_age_s = await self._queue.get()
            if max_age_s is not None and time.monotonic() - queued_at > max_age_s:
                log.info("dropped stale line: %r", text)
                continue
            try:
                await self._say(text)
            except Exception:
                log.exception("failed to say %r", text)

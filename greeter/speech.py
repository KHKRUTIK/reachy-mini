"""Strictly ordered, one-at-a-time speech."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


class SpeechQueue:
    def __init__(self, say: Callable[[str], Awaitable[None]]) -> None:
        self._say = say
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def put(self, text: str) -> None:
        await self._queue.put(text)

    async def run(self) -> None:
        while True:
            text = await self._queue.get()
            try:
                await self._say(text)
            except Exception:
                log.exception("failed to say %r", text)

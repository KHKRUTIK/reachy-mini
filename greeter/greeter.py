"""What Reachy does for each scan result and each face update."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from greeter.arrival import ArrivalPrompter
from greeter.checkin import CheckinGate, ScanResult
from greeter.lines import FRONT_DESK_LINE, QR_PROMPT_LINE, WRONG_CODE_LINE, welcome_back_line, welcome_line

log = logging.getLogger(__name__)


class Greeter:
    def __init__(
        self,
        speech: Any,
        moves: Any,
        gate: CheckinGate,
        arrival: ArrivalPrompter,
        get_compliment: Callable[[], Awaitable[str | None]],
        compliment_window_s: float = 4.0,
    ) -> None:
        self._speech = speech
        self._moves = moves
        self._gate = gate
        self._arrival = arrival
        self._get_compliment = get_compliment
        self._compliment_window_s = compliment_window_s
        self._tasks: set[asyncio.Task] = set()
        self.moving = False
        self.on_qr_prompt: Callable[[float], None] | None = None

    async def handle_scan(self, r: ScanResult) -> None:
        self._arrival.note_scan(r.at)
        decision = self._gate.decide(r)
        log.info("scan %s %r -> %s", r.kind, r.name, decision)
        if decision == "welcome":
            await self._speech.put(welcome_line(r.name))  # queued first: the compliment can never jump ahead
            self._spawn(self._compliment_after_welcome())
            self._spawn(self._move(self._moves.welcome))
        elif decision == "welcome_back":
            await self._speech.put(welcome_back_line(r.name))
            self._spawn(self._move(self._moves.welcome))
        elif decision == "front_desk":
            await self._speech.put(FRONT_DESK_LINE)
            self._spawn(self._move(self._moves.front_desk))
        elif decision == "wrong_code":
            await self._speech.put(WRONG_CODE_LINE)

    async def handle_face(self, present: bool, now: float) -> None:
        if self.moving:
            return
        if self._arrival.update(present, now):
            await self._speech.put(QR_PROMPT_LINE)
            self._spawn(self._move(self._moves.perk_up))
            if self.on_qr_prompt:
                self.on_qr_prompt(now)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _compliment_after_welcome(self) -> None:
        try:
            text = await asyncio.wait_for(self._get_compliment(), self._compliment_window_s)
        except asyncio.TimeoutError:
            log.info("compliment too slow; dropped")
            return
        if text:
            await self._speech.put(text)

    async def _move(self, fn: Callable[[], Awaitable[None]]) -> None:
        self.moving = True
        try:
            await fn()
        except Exception:
            log.exception("move failed")
        finally:
            self.moving = False

    def _spawn(self, coro: Awaitable[None]) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

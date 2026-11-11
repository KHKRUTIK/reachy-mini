"""Short expressive moves. Daemon head tracking is paused during each move so they don't fight."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx
import numpy as np
from reachy_mini.utils import create_head_pose

log = logging.getLogger(__name__)

# Where Reachy looks when hunting for someone: body turns, head level (degrees, 0 = straight ahead).
SEARCH_YAWS_DEG = [-40, -80, -40, 0, 40, 80, 40]


def _pose(pitch=0.0, roll=0.0, yaw=0.0):
    return create_head_pose(pitch=pitch, roll=roll, yaw=yaw, degrees=True)


class Moves:
    def __init__(self, mini: Any, daemon_url: str) -> None:
        self._mini = mini
        self._daemon = daemon_url.rstrip("/")

    async def welcome(self) -> None:
        """Antennas up with a wiggle and a small happy nod (~1.4 s)."""
        await self._sequence([
            (dict(head=_pose(pitch=-8), antennas=np.deg2rad([40, -40])), 0.35),
            (dict(antennas=np.deg2rad([15, -15])), 0.2),
            (dict(head=_pose(pitch=6), antennas=np.deg2rad([40, -40])), 0.35),
            (dict(head=_pose(), antennas=[0.0, 0.0]), 0.5),
        ])

    async def front_desk(self) -> None:
        """Gentle sympathetic tilt with antennas drooping (~1.3 s)."""
        await self._sequence([
            (dict(head=_pose(roll=12, pitch=4), antennas=np.deg2rad([-30, 30])), 0.6),
            (dict(head=_pose(), antennas=[0.0, 0.0]), 0.7),
        ])

    async def sad(self) -> None:
        """Head drops, antennas droop, a slow little shake, then a hopeful recovery (~4 s)."""
        await self._sequence([
            (dict(head=_pose(pitch=22), antennas=np.deg2rad([-70, 70])), 1.0),
            (dict(head=_pose(pitch=24, roll=-6)), 0.6),
            (dict(head=_pose(pitch=24, roll=6)), 0.8),
            (dict(head=_pose(pitch=20)), 0.6),
            (dict(head=_pose(), antennas=[0.0, 0.0]), 1.0),
        ])

    async def perk_up(self) -> None:
        """Small curious antenna lift (~0.8 s)."""
        await self._sequence([
            (dict(antennas=np.deg2rad([25, -25])), 0.3),
            (dict(antennas=[0.0, 0.0]), 0.5),
        ])

    async def search(self, found: Callable[[], bool]) -> bool:
        """Turn side to side until ``found()`` sees a face; then hand back to face tracking. ~6 s at most."""
        await self._tracking(False)
        try:
            for yaw in SEARCH_YAWS_DEG:
                await asyncio.to_thread(
                    self._mini.goto_target, head=_pose(), antennas=np.deg2rad([20, -20]),
                    body_yaw=float(np.deg2rad(yaw)), duration=0.7,
                )
                if await asyncio.to_thread(found):
                    log.info("search: found someone at %d deg", yaw)
                    return True  # stay facing them; tracking takes over
            await asyncio.to_thread(self._mini.goto_target, head=_pose(), antennas=[0.0, 0.0], body_yaw=0.0, duration=0.8)
            log.info("search: nobody found")
            return False
        finally:
            await self._tracking(True)

    async def _sequence(self, steps: list[tuple[dict, float]]) -> None:
        await self._tracking(False)
        try:
            for kwargs, duration in steps:
                await asyncio.to_thread(self._mini.goto_target, duration=duration, **kwargs)
        finally:
            await self._tracking(True)

    async def _tracking(self, enabled: bool) -> None:
        path = "enable" if enabled else "disable"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(f"{self._daemon}/api/media/tracking/{path}")
        except httpx.HTTPError as e:
            log.warning("could not %s head tracking: %s", path, e)

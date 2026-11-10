"""Short expressive moves. Daemon head tracking is paused during each move so they don't fight."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import numpy as np
from reachy_mini.utils import create_head_pose

log = logging.getLogger(__name__)


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

    async def perk_up(self) -> None:
        """Small curious antenna lift (~0.8 s)."""
        await self._sequence([
            (dict(antennas=np.deg2rad([25, -25])), 0.3),
            (dict(antennas=[0.0, 0.0]), 0.5),
        ])

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

"""Decide what Reachy says for each Luma scanner result."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Decision = Literal["welcome", "front_desk", "ignore"]


@dataclass(frozen=True)
class ScanResult:
    kind: Literal["success", "failure"]
    name: str | None
    at: float  # monotonic seconds


def _key(name: str | None) -> str | None:
    return name.casefold().strip() if name else None


class CheckinGate:
    """Suppresses repeat reads of a ticket that is still being held up."""

    def __init__(self, repeat_window_s: float = 60.0, failure_repeat_s: float = 15.0) -> None:
        self._repeat_window_s = repeat_window_s
        self._failure_repeat_s = failure_repeat_s
        self._welcomed: dict[str, float] = {}
        self._front_desk: dict[str | None, float] = {}

    def decide(self, r: ScanResult) -> Decision:
        self._prune(r.at)
        key = _key(r.name)
        if key is not None and key in self._welcomed:
            return "ignore"
        if r.kind == "success":
            if key is not None:
                self._welcomed[key] = r.at
            return "welcome"
        if key in self._front_desk:
            return "ignore"
        self._front_desk[key] = r.at
        return "front_desk"

    def _prune(self, now: float) -> None:
        self._welcomed = {k: t for k, t in self._welcomed.items() if now - t < self._repeat_window_s}
        self._front_desk = {k: t for k, t in self._front_desk.items() if now - t < self._failure_repeat_s}

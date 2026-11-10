"""Decide when to ask a newly arrived person for their QR code."""
from __future__ import annotations

import math


class ArrivalPrompter:
    """One prompt per visit, after a dwell with no scan, rate-limited by a cooldown.

    A visit starts when a face appears after more than ``flicker_s`` of absence,
    measured from the first absent sample to the next present one. Any scan blocks
    prompting for ``scan_block_s`` (someone is clearly already using the scanner).
    """

    def __init__(
        self,
        dwell_s: float = 4.0,
        cooldown_s: float = 60.0,
        flicker_s: float = 5.0,
        scan_block_s: float = 60.0,
    ) -> None:
        self._dwell_s = dwell_s
        self._cooldown_s = cooldown_s
        self._flicker_s = flicker_s
        self._scan_block_s = scan_block_s
        self._visit_start: float | None = None
        self._absent_since: float | None = None
        self._prompted = False
        self._scanned = False
        self._last_prompt = -math.inf
        self._last_scan = -math.inf

    def update(self, face_present: bool, now: float, can_prompt: bool = True) -> bool:
        if not face_present:
            if self._absent_since is None:
                self._absent_since = now
            return False

        gone_too_long = self._absent_since is not None and now - self._absent_since > self._flicker_s
        if self._visit_start is None or gone_too_long:
            self._visit_start = now
            self._prompted = False
            self._scanned = False
        self._absent_since = None

        if (
            can_prompt
            and not self._prompted
            and not self._scanned
            and now - self._visit_start >= self._dwell_s
            and now - self._last_prompt >= self._cooldown_s
            and now - self._last_scan >= self._scan_block_s
        ):
            self._prompted = True
            self._last_prompt = now
            return True
        return False

    def note_scan(self, now: float) -> None:
        self._scanned = True
        self._last_scan = now

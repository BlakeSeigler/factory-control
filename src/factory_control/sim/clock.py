"""Simulation clock. Sim time is what every OPC UA SourceTimestamp carries (D-07)."""

from __future__ import annotations

import time


class SimClock:
    """Monotonic sim time, anchored to wall-clock unix time at start.

    ``now`` is unix seconds so timestamps stay human-readable in the DB. With
    ``time_scale != 1`` sim time diverges from wall time by design.
    """

    def __init__(self, start_unix: float | None = None) -> None:
        self._t0 = time.time() if start_unix is None else start_unix
        self._elapsed = 0.0

    @property
    def now(self) -> float:
        return self._t0 + self._elapsed

    @property
    def elapsed(self) -> float:
        return self._elapsed

    def advance(self, dt: float) -> None:
        self._elapsed += dt

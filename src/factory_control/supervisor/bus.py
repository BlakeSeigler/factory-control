"""In-process fan-out of samples to independent consumers.

Each consumer gets its own bounded queue so a slow consumer (e.g. the historian
during a disk stall) cannot block the analyzer. On overflow the oldest item is
dropped and counted: for a monitoring system, stale data is worth less than
fresh data. Whether any consumer must be lossless is D-31.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


class Bus[T]:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._maxsize = maxsize
        self._queues: dict[str, asyncio.Queue[T]] = {}
        self.dropped: dict[str, int] = {}

    def subscribe(self, name: str) -> asyncio.Queue[T]:
        q: asyncio.Queue[T] = asyncio.Queue(self._maxsize)
        self._queues[name] = q
        self.dropped[name] = 0
        return q

    def publish(self, item: T) -> None:
        for name, q in self._queues.items():
            if q.full():
                q.get_nowait()
                self.dropped[name] += 1
                if self.dropped[name] % 1000 == 1:
                    log.warning("bus consumer %s is behind; %d dropped", name, self.dropped[name])
            q.put_nowait(item)

"""In-process fan-out of samples to independent consumers.

Each consumer gets its own bounded queue so a slow consumer (e.g. the historian
during a disk stall) cannot block the analyzer. On overflow the oldest item is
dropped and counted: for monitoring, stale data is worth less than fresh data.
Whether any consumer must be lossless is D-31.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)


class Bus[ItemT]:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._maxsize = maxsize
        self._queues: dict[str, asyncio.Queue[ItemT]] = {}
        self.dropped: dict[str, int] = {}

    def subscribe(self, name: str) -> asyncio.Queue[ItemT]:
        q: asyncio.Queue[ItemT] = asyncio.Queue(self._maxsize)
        self._queues[name] = q
        self.dropped[name] = 0
        return q

    def publish(self, item: ItemT) -> None:
        for name, q in self._queues.items():
            if q.full():
                q.get_nowait()
                self.dropped[name] += 1
                if self.dropped[name] % 1000 == 1:
                    log.warning("bus consumer %s is behind; %d dropped", name, self.dropped[name])
            q.put_nowait(item)


async def consume[ItemT](
    queue: asyncio.Queue[ItemT],
    on_item: Callable[[ItemT], Awaitable[None]],
    on_tick: Callable[[], Awaitable[None]],
    tick_period_s: float,
) -> None:
    """Handle queue items as they arrive and call ``on_tick`` every ``tick_period_s``."""
    loop = asyncio.get_running_loop()
    next_tick = loop.time() + tick_period_s
    while True:
        with contextlib.suppress(TimeoutError):
            await on_item(await asyncio.wait_for(queue.get(), max(0.0, next_tick - loop.time())))
        if loop.time() >= next_tick:
            await on_tick()
            next_tick = loop.time() + tick_period_s

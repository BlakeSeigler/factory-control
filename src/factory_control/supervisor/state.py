"""Latest-value cache per machine; the controller's view of the line."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from factory_control.common.messages import Sample


class StateCache:
    def __init__(self) -> None:
        self.latest: dict[str, dict[str, tuple[float, Any]]] = defaultdict(dict)
        self.now = 0.0  # newest source timestamp seen (sim time)

    def get(self, machine_id: str, tag: str) -> Any | None:
        entry = self.latest.get(machine_id, {}).get(tag)
        return entry[1] if entry else None

    async def run(self, queue: asyncio.Queue[Sample]) -> None:
        while True:
            s = await queue.get()
            self.latest[s.machine_id][s.tag] = (s.source_ts, s.value)
            self.now = max(self.now, s.source_ts)

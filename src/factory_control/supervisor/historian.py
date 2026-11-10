"""Persists samples, alarms, setpoint commands and sim ground truth to SQLite."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample, SetpointCommand
from factory_control.storage.db import Database, SampleRow
from factory_control.supervisor.client import GROUND_TRUTH_TAG

log = logging.getLogger(__name__)


class Historian:
    def __init__(self, db: Database, flush_period_s: float) -> None:
        self.db = db
        self.flush_period_s = flush_period_s
        self._rows: list[SampleRow] = []
        self._last_truth: dict[str, str] = {}

    def _accept(self, s: Sample) -> None:
        if s.tag == GROUND_TRUTH_TAG:
            if self._last_truth.get(s.machine_id) != s.value:  # store transitions only
                self._last_truth[s.machine_id] = s.value
                self.db.insert_ground_truth(s.source_ts, s.machine_id, str(s.value))
            return
        tag = T.TAGS_BY_KEY.get(s.tag)
        if tag is None or not tag.historize:
            # TODO(D-17): vibration waveform retention policy (store raw / features / on alarm).
            return
        self._rows.append((s.source_ts, s.machine_id, s.tag, float(s.value), s.status))

    async def run(self, queue: asyncio.Queue[Sample]) -> None:
        loop = asyncio.get_running_loop()
        next_flush = loop.time() + self.flush_period_s
        while True:
            timeout = max(0.0, next_flush - loop.time())
            with contextlib.suppress(TimeoutError):
                self._accept(await asyncio.wait_for(queue.get(), timeout))
            if loop.time() >= next_flush:
                await self.flush()
                next_flush = loop.time() + self.flush_period_s

    async def flush(self) -> None:
        if not self._rows:
            return
        rows, self._rows = self._rows, []
        await asyncio.to_thread(self.db.insert_samples, rows)

    async def record_alarm(self, ev: AlarmEvent) -> None:
        await asyncio.to_thread(self.db.insert_alarm_event, ev)

    async def record_setpoint(self, cmd: SetpointCommand) -> None:
        await asyncio.to_thread(self.db.insert_setpoint_command, cmd)

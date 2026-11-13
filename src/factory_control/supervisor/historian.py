"""Persists samples, alarms, setpoint commands and sim ground truth to SQLite.

Samples and ground truth are buffered and written in one batch per flush period,
off the event loop.
"""

from __future__ import annotations

import asyncio
import logging

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample, SetpointCommand
from factory_control.storage.db import Database, SampleRow, TruthRow
from factory_control.supervisor.bus import consume

log = logging.getLogger(__name__)


class Historian:
    def __init__(self, db: Database, flush_period_s: float) -> None:
        self.db = db
        self.flush_period_s = flush_period_s
        self._samples: list[SampleRow] = []
        self._truth: list[TruthRow] = []
        self._last_truth: dict[str, str] = {}

    async def _accept(self, s: Sample) -> None:
        if s.tag == T.GROUND_TRUTH_KEY:
            if self._last_truth.get(s.device_id) != s.value:  # store transitions only
                self._last_truth[s.device_id] = s.value
                self._truth.append((s.source_ts, s.device_id, str(s.value)))
            return
        tag = T.ALL_TAGS.get(s.tag)
        if tag is None or not tag.historize:
            return  # TODO(D-30): vibration waveform retention
        self._samples.append((s.source_ts, s.device_id, s.tag, float(s.value), s.status))

    async def run(self, queue: asyncio.Queue[Sample]) -> None:
        await consume(queue, self._accept, self.flush, self.flush_period_s)

    async def flush(self) -> None:
        if not (self._samples or self._truth):
            return
        samples, self._samples = self._samples, []
        truth, self._truth = self._truth, []
        await asyncio.to_thread(self.db.insert_batch, samples, truth)

    async def record_alarm(self, ev: AlarmEvent) -> None:
        await asyncio.to_thread(self.db.insert_alarm_event, ev)

    async def record_setpoints(self, cmds: list[SetpointCommand]) -> None:
        await asyncio.to_thread(self.db.insert_setpoint_commands, cmds)

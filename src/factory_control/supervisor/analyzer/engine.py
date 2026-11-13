"""Routes samples to per-device rule instances and forwards alarm events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from factory_control.common.messages import AlarmEvent, Sample
from factory_control.supervisor.analyzer.base import Rule
from factory_control.supervisor.analyzer.overtemp import OvertempRule
from factory_control.supervisor.analyzer.setpoint_tracking import SetpointTrackingRule
from factory_control.supervisor.analyzer.vibration import VibrationAnomalyRule
from factory_control.supervisor.bus import consume

log = logging.getLogger(__name__)

AlarmSink = Callable[[AlarmEvent], Awaitable[None]]
RULES: tuple[type[Rule], ...] = (SetpointTrackingRule, OvertempRule, VibrationAnomalyRule)


class AnalyzerEngine:
    def __init__(self, device_tags: dict[str, frozenset[str]], sink: AlarmSink) -> None:
        self.rules: dict[str, list[Rule]] = {
            d: [r(d) for r in RULES if r.requires <= tags] for d, tags in device_tags.items()
        }
        for d, rules in self.rules.items():
            log.info("analyzer rules for %s: %s", d, [r.name for r in rules] or "none")
        self.sink = sink
        self.sample_time: dict[str, float] = dict.fromkeys(device_tags, 0.0)

    async def _emit(self, events: list[AlarmEvent]) -> None:
        for ev in events:
            log.warning("ALARM %s %s %s: %s", ev.device_id, ev.rule, ev.transition, ev.message)
            await self.sink(ev)

    async def _on_sample(self, s: Sample) -> None:
        if s.device_id not in self.rules:
            return
        self.sample_time[s.device_id] = max(self.sample_time[s.device_id], s.source_ts)
        for rule in self.rules[s.device_id]:
            if s.tag in rule.inputs:
                await self._emit(rule.on_sample(s))

    async def _on_tick(self) -> None:
        for device_id, rules in self.rules.items():
            for rule in rules:
                await self._emit(rule.on_tick(self.sample_time[device_id]))

    async def run(self, queue: asyncio.Queue[Sample], tick_period_s: float = 0.5) -> None:
        await consume(queue, self._on_sample, self._on_tick, tick_period_s)

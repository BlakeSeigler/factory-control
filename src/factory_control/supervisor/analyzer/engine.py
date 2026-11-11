"""Routes samples to per-machine rule instances and forwards alarm events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import AnalyzerConfig
from factory_control.supervisor.analyzer.base import Rule
from factory_control.supervisor.analyzer.overcurrent import OvercurrentRule
from factory_control.supervisor.analyzer.overtemp import OvertempRule
from factory_control.supervisor.analyzer.setpoint_tracking import SetpointTrackingRule
from factory_control.supervisor.analyzer.vibration import VibrationAnomalyRule

log = logging.getLogger(__name__)

AlarmSink = Callable[[AlarmEvent], Awaitable[None]]


def build_rules(machine_id: str, cfg: AnalyzerConfig) -> list[Rule]:
    return [
        SetpointTrackingRule(machine_id, cfg.setpoint_tracking),
        OvertempRule(machine_id, cfg.overtemp),
        VibrationAnomalyRule(machine_id, cfg.vibration),
        OvercurrentRule(machine_id, cfg.overcurrent),
    ]


class AnalyzerEngine:
    def __init__(self, machine_ids: list[str], cfg: AnalyzerConfig, sink: AlarmSink) -> None:
        self.rules: dict[str, list[Rule]] = {m: build_rules(m, cfg) for m in machine_ids}
        if not cfg.overcurrent.configured:
            log.warning("overcurrent rule disabled: no limits configured (D-25)")
        self.sink = sink
        self.sample_time: dict[str, float] = dict.fromkeys(machine_ids, 0.0)

    async def _emit(self, events: list[AlarmEvent]) -> None:
        for ev in events:
            log.warning("ALARM %s %s %s: %s", ev.machine_id, ev.rule, ev.transition, ev.message)
            await self.sink(ev)

    async def run(self, queue: asyncio.Queue[Sample], tick_period_s: float = 0.5) -> None:
        loop = asyncio.get_running_loop()
        next_tick = loop.time() + tick_period_s
        while True:
            try:
                s = await asyncio.wait_for(queue.get(), max(0.0, next_tick - loop.time()))
            except TimeoutError:
                s = None
            if s is not None and s.machine_id in self.rules:
                self.sample_time[s.machine_id] = max(self.sample_time[s.machine_id], s.source_ts)
                for rule in self.rules[s.machine_id]:
                    if s.tag in rule.inputs:
                        await self._emit(rule.on_sample(s))
            if loop.time() >= next_tick:
                for mid, rules in self.rules.items():
                    for rule in rules:
                        await self._emit(rule.on_tick(self.sample_time[mid]))
                next_tick = loop.time() + tick_period_s

"""Routes samples to per-device rule instances and forwards alarm events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import AnalyzerConfig
from factory_control.supervisor.analyzer.base import Rule
from factory_control.supervisor.analyzer.overtemp import OvertempRule
from factory_control.supervisor.analyzer.setpoint_tracking import SetpointTrackingRule
from factory_control.supervisor.analyzer.vibration import VibrationAnomalyRule

log = logging.getLogger(__name__)

AlarmSink = Callable[[AlarmEvent], Awaitable[None]]


def build_rules(device_id: str, device_tags: frozenset[str], cfg: AnalyzerConfig) -> list[Rule]:
    candidates: list[Rule] = [
        SetpointTrackingRule(device_id, cfg.setpoint_tracking),
        OvertempRule(device_id, cfg.overtemp),
        VibrationAnomalyRule(device_id, cfg.vibration),
    ]
    return [r for r in candidates if r.requires <= device_tags]


class AnalyzerEngine:
    def __init__(
        self, device_tags: dict[str, frozenset[str]], cfg: AnalyzerConfig, sink: AlarmSink
    ) -> None:
        self.rules: dict[str, list[Rule]] = {
            d: build_rules(d, tags, cfg) for d, tags in device_tags.items()
        }
        for d, rules in self.rules.items():
            log.info("analyzer rules for %s: %s", d, [r.name for r in rules] or "none")
        self.sink = sink
        self.sample_time: dict[str, float] = dict.fromkeys(device_tags, 0.0)

    async def _emit(self, events: list[AlarmEvent]) -> None:
        for ev in events:
            log.warning("ALARM %s %s %s: %s", ev.device_id, ev.rule, ev.transition, ev.message)
            await self.sink(ev)

    async def run(self, queue: asyncio.Queue[Sample], tick_period_s: float = 0.5) -> None:
        loop = asyncio.get_running_loop()
        next_tick = loop.time() + tick_period_s
        while True:
            try:
                s = await asyncio.wait_for(queue.get(), max(0.0, next_tick - loop.time()))
            except TimeoutError:
                s = None
            if s is not None and s.device_id in self.rules:
                self.sample_time[s.device_id] = max(self.sample_time[s.device_id], s.source_ts)
                for rule in self.rules[s.device_id]:
                    if s.tag in rule.inputs:
                        await self._emit(rule.on_sample(s))
            if loop.time() >= next_tick:
                for mid, rules in self.rules.items():
                    for rule in rules:
                        await self._emit(rule.on_tick(self.sample_time[mid]))
                next_tick = loop.time() + tick_period_s

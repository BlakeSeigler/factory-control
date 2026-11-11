"""Simulator process: the whole line in one asyncio loop, one PLC + OPC UA server per device.

Timing (D-06): physics advances in fixed steps of ``physics_dt_s`` of sim time and
every PLC scans once per step; values are published every ``publish_period_s``;
vibration blocks every ``block_size / sample_rate_hz``. Wall-clock pacing is
``sim_dt / time_scale`` with absolute deadlines, so pacing does not drift.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import yaml

from factory_control.config import AppConfig
from factory_control.plc import build_plc
from factory_control.sim.clock import SimClock
from factory_control.sim.faults import Scenario
from factory_control.sim.line import Line

log = logging.getLogger(__name__)


def load_scenario(path: Path | str | None) -> Scenario:
    if path is None:
        return Scenario(name="none")
    with open(path) as f:
        return Scenario.model_validate(yaml.safe_load(f))


class ScenarioPlayer:
    def __init__(self, scenario: Scenario, line: Line) -> None:
        self.line = line
        self.pending = sorted(scenario.events, key=lambda e: e.at_s)

    def apply_due(self, elapsed_s: float) -> None:
        while self.pending and self.pending[0].at_s <= elapsed_s:
            ev = self.pending.pop(0)
            fm = self.line.devices[ev.device].faults
            if ev.action == "inject":
                fm.inject(ev.fault, ev.params)
            else:
                fm.clear(ev.fault)
            log.warning("scenario t=%.1fs %s %s %s", ev.at_s, ev.action, ev.device, ev.fault)


async def run_simulator(
    cfg: AppConfig, scenario: Scenario, stop: asyncio.Event | None = None
) -> None:
    stop = stop or asyncio.Event()
    clock = SimClock()
    line = Line(cfg, clock)
    player = ScenarioPlayer(scenario, line)
    plcs = {did: build_plc(cfg.device(did), plant, clock) for did, plant in line.devices.items()}

    for plc in plcs.values():
        await plc.init()
    for plc in plcs.values():
        await plc.start()

    dt = cfg.sim.physics_dt_s
    steps_per_publish = max(1, round(cfg.sim.publish_period_s / dt))
    next_vib = dict.fromkeys(plcs, 0.0)
    wall_per_tick = steps_per_publish * dt / cfg.sim.time_scale
    deadline = time.monotonic()

    try:
        while not stop.is_set():
            for _ in range(steps_per_publish):
                for plc in plcs.values():
                    plc.apply_client_writes()
                    plc.local_logic(dt)
                player.apply_due(clock.elapsed)
                line.step(dt)

            now = clock.now
            for did, plc in plcs.items():
                await plc.publish(now)
                if clock.elapsed >= next_vib[did]:
                    period = await plc.publish_vibration(now)
                    next_vib[did] = float("inf") if period is None else next_vib[did] + period

            deadline += wall_per_tick
            delay = deadline - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            elif delay < -1.0:
                log.warning("simulator %.2fs behind real time; resyncing", -delay)
                deadline = time.monotonic()
    finally:
        for plc in plcs.values():
            await plc.stop()

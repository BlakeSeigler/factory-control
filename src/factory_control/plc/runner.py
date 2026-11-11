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


async def run_simulator(
    cfg: AppConfig, scenario: Scenario, stop: asyncio.Event | None = None
) -> None:
    stop = stop or asyncio.Event()
    clock = SimClock()
    line = Line(cfg, clock)
    del scenario  # TODO: scenario playback (docs/fault-injection.md section 1)
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

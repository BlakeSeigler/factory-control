"""Supervisor process wiring."""

from __future__ import annotations

import asyncio
import logging

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import AppConfig
from factory_control.storage.db import Database
from factory_control.supervisor.analyzer.engine import AnalyzerEngine
from factory_control.supervisor.bus import Bus
from factory_control.supervisor.client import DeviceClient
from factory_control.supervisor.control.base import Controller, LineTarget, ManualController
from factory_control.supervisor.control.baseline import BaselineController
from factory_control.supervisor.control.mpc import MpcController
from factory_control.supervisor.historian import Historian
from factory_control.supervisor.state import StateCache

log = logging.getLogger(__name__)


def _build_controller(cfg: AppConfig) -> Controller:
    return {
        "manual": ManualController,
        "baseline": BaselineController,
        "mpc": MpcController,
    }[cfg.supervisor.control.mode]()


async def _control_loop(
    cfg: AppConfig,
    controller: Controller,
    state: StateCache,
    clients: dict[str, DeviceClient],
    historian: Historian,
) -> None:
    target: LineTarget | None = None  # TODO(D-45): runtime source of the line target
    while True:
        await asyncio.sleep(cfg.supervisor.control.period_s)
        for cmd in controller.step(state.now, state, target):
            client = clients[cmd.device_id]
            if not client.connected.is_set():
                log.warning("dropping setpoint for disconnected %s", cmd.device_id)
                continue
            await client.write(cmd.tag, cmd.value)
            await historian.record_setpoint(cmd)


async def run_supervisor(cfg: AppConfig, stop: asyncio.Event | None = None) -> None:
    stop = stop or asyncio.Event()
    sc = cfg.supervisor

    db = Database(sc.db_path)
    db.init_schema()
    db.upsert_devices((d.id, d.type, d.opcua.endpoint) for d in cfg.devices)

    bus: Bus[Sample] = Bus()
    historian = Historian(db, sc.historian_flush_period_s)
    state = StateCache()

    async def on_alarm(ev: AlarmEvent) -> None:
        await historian.record_alarm(ev)

    device_tags = {
        d.id: frozenset(t.key for t in T.tags_for(d.type, d.instruments)) for d in cfg.devices
    }
    analyzer = AnalyzerEngine(device_tags, sc.analyzer, on_alarm)
    clients = {d.id: DeviceClient(d, bus, period_ms=sc.subscription_period_ms) for d in cfg.devices}

    tasks = [
        asyncio.create_task(historian.run(bus.subscribe("historian")), name="historian"),
        asyncio.create_task(state.run(bus.subscribe("state")), name="state"),
        asyncio.create_task(analyzer.run(bus.subscribe("analyzer")), name="analyzer"),
        asyncio.create_task(
            _control_loop(cfg, _build_controller(cfg), state, clients, historian), name="control"
        ),
        *(asyncio.create_task(c.run(stop), name=f"client:{did}") for did, c in clients.items()),
    ]
    stopper = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if t is not stopper and t.exception():
                raise t.exception()  # a component crashed: fail loudly, do not limp on
    finally:
        for t in [*tasks, stopper]:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await historian.flush()
        db.close()

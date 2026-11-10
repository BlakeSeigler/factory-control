"""Simulator + supervisor in one event loop on non-default ports: a setpoint written
over OPC UA must move the simulated motor and land in the historian."""

import asyncio
import contextlib

from factory_control.common import tags as T
from factory_control.config import load_config
from factory_control.machine.runner import load_scenario, run_simulator
from factory_control.storage.db import Database
from factory_control.supervisor.app import run_supervisor


def _test_config(tmp_path):
    cfg = load_config("config/line.yaml")
    machines = [
        m.model_copy(
            update={
                "opcua": m.opcua.model_copy(
                    update={"endpoint": f"opc.tcp://127.0.0.1:{48500 + i}/test/{m.id}"}
                )
            }
        )
        for i, m in enumerate(cfg.machines)
    ]
    sup = cfg.supervisor.model_copy(
        update={"db_path": tmp_path / "t.db", "historian_flush_period_s": 0.2}
    )
    return cfg.model_copy(update={"machines": machines, "supervisor": sup})


async def test_setpoint_round_trip(tmp_path):
    cfg = _test_config(tmp_path)
    stop = asyncio.Event()
    sim = asyncio.create_task(run_simulator(cfg, load_scenario(None), stop))
    await asyncio.sleep(1.0)
    sup = asyncio.create_task(run_supervisor(cfg, stop))
    try:
        from factory_control.cli import _setpoint

        await asyncio.sleep(2.0)
        await _setpoint(cfg, "feeder_1", 600.0)
        await asyncio.sleep(4.0)
    finally:
        stop.set()
        for t in (sup, sim):
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(t, 10)

    db = Database(cfg.supervisor.db_path, readonly=True)
    speeds = [v for _, v in db.series("feeder_1", T.SPEED.key, 0)]
    setpoints = [v for _, v in db.series("feeder_1", T.SPEED_SETPOINT.key, 0)]
    db.close()
    assert 600.0 in setpoints
    assert speeds and 550 < speeds[-1] <= 600.0

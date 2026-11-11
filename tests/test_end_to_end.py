"""Simulator (4 PLCs) + supervisor in one event loop on non-default ports: writes over
OPC UA must reach the plant/PLC and everything must land in the historian."""

import asyncio
import contextlib

from factory_control.cli import write_tag
from factory_control.common import tags as T
from factory_control.config import load_config
from factory_control.plc.runner import load_scenario, run_simulator
from factory_control.storage.db import Database
from factory_control.supervisor.app import run_supervisor


def _test_config(tmp_path):
    cfg = load_config("config/line.yaml")
    devices = [
        d.model_copy(
            update={
                "opcua": d.opcua.model_copy(
                    update={"endpoint": f"opc.tcp://127.0.0.1:{48500 + i}/test/{d.id}"}
                )
            }
        )
        for i, d in enumerate(cfg.devices)
    ]
    sup = cfg.supervisor.model_copy(
        update={"db_path": tmp_path / "t.db", "historian_flush_period_s": 0.2}
    )
    return cfg.model_copy(update={"devices": devices, "supervisor": sup})


async def _wait_for_servers(cfg, timeout_s: float = 20.0) -> None:
    """Each asyncua server takes ~1 s to initialize; wait until all accept connections."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    for d in cfg.devices:
        host, port = d.opcua.endpoint.split("//")[1].split("/")[0].split(":")
        while True:
            try:
                _, w = await asyncio.open_connection(host, int(port))
                w.close()
                break
            except OSError:
                assert loop.time() < deadline, f"{d.id} PLC never came up"
                await asyncio.sleep(0.2)


async def _wait_for_samples(db_path, device_ids, sup_task, timeout_s: float = 20.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while True:
        if sup_task.done():
            sup_task.result()  # surface the supervisor's exception immediately
        if db_path.exists():
            db = Database(db_path, readonly=True)
            try:
                seen = {r[0] for r in db.conn.execute("SELECT DISTINCT device_id FROM sample")}
            finally:
                db.close()
            if seen >= set(device_ids):
                return
        assert loop.time() < deadline, "supervisor never received data from every device"
        await asyncio.sleep(0.2)


async def test_round_trip_all_devices(tmp_path):
    cfg = _test_config(tmp_path)
    stop = asyncio.Event()
    sim = asyncio.create_task(run_simulator(cfg, load_scenario(None), stop))
    await _wait_for_servers(cfg)
    sup = asyncio.create_task(run_supervisor(cfg, stop))
    try:
        await _wait_for_samples(cfg.supervisor.db_path, [d.id for d in cfg.devices], sup)
        await write_tag(cfg, "extruder", T.SPEED_SETPOINT.key, 600.0)
        await write_tag(cfg, "extruder", T.BARREL_SETPOINT.key, 210.0)
        await asyncio.sleep(4.0)
    finally:
        stop.set()
        for t in (sup, sim):
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(t, 10)

    db = Database(cfg.supervisor.db_path, readonly=True)
    try:

        def values(dev, tag):
            return [v for _, v in db.series(dev, tag.key, 0)]

        speeds = values("extruder", T.SPEED)
        assert 600.0 in values("extruder", T.SPEED_SETPOINT)
        assert speeds and 550 < speeds[-1] <= 600.0
        assert 210.0 in values("extruder", T.BARREL_SETPOINT)
        assert values("extruder", T.HEATER_OUTPUT), "PLC-computed PID output is published"
        assert values("shredder", T.HOPPER_WEIGHT), "load cell reaches the historian"
        assert not values("extruder", T.HOPPER_WEIGHT)
        assert values("water_bath", T.BATH_TEMP)
        assert values("pelletizer", T.SPEED)
    finally:
        db.close()

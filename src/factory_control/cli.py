"""Command-line entry point: ``fc <command>``.

fc sim [--scenario FILE]          run the simulated line (one PLC/OPC UA server per device)
fc supervisor                     run clients + historian + analyzer + controller
fc dashboard                      serve the web dashboard
fc write DEVICE TAG VALUE         write a writable tag on a device's PLC, e.g.
                                    fc write extruder motor.speed_setpoint_rpm 900
                                    fc write extruder barrel.temperature_setpoint_c 210
fc fault DEVICE KIND [JSON]       inject a fault (simulator only)
fc clear-faults DEVICE            clear all injected faults (simulator only)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from factory_control.common import tags as T
from factory_control.common.logging import setup_logging
from factory_control.config import DEFAULT_CONFIG_PATH, AppConfig, load_config


async def _with_device(cfg: AppConfig, device_id: str, fn: Callable[[Any], Awaitable[Any]]) -> Any:
    from asyncua import Client

    client = Client(cfg.device(device_id).opcua.endpoint, timeout=4)
    client.session_timeout = 30_000
    async with client:
        return await fn(client)


async def write_tag(cfg: AppConfig, device_id: str, tag_key: str, value: float) -> None:
    from asyncua import ua

    from factory_control.supervisor.client import resolve_tag_node

    dev = cfg.device(device_id)
    writable = {t.key for t in T.tags_for(dev.type, dev.instruments) if t.writable}
    if tag_key not in writable:
        raise SystemExit(
            f"{device_id} has no writable tag {tag_key!r}; options: {sorted(writable)}"
        )

    async def go(client: Any) -> None:
        node = await resolve_tag_node(client, dev.type, T.ALL_TAGS[tag_key])
        await node.write_value(ua.Variant(float(value), ua.VariantType.Double))

    await _with_device(cfg, device_id, go)
    print(f"{device_id}: {tag_key} = {value}")


async def _sim_method(cfg: AppConfig, device_id: str, method: str, *args: str) -> None:
    async def go(client: Any) -> Any:
        ns = await client.get_namespace_index(T.SIM_NS_URI)
        sim = await client.nodes.objects.get_child([f"{ns}:{T.SIM_OBJECT}"])
        return await sim.call_method(f"{ns}:{method}", *args)

    print(f"{device_id}: {method} -> {await _with_device(cfg, device_id, go)}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="fc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sim")
    s.add_argument("--scenario", type=Path)
    sub.add_parser("supervisor")
    sub.add_parser("dashboard")
    s = sub.add_parser("write")
    s.add_argument("device")
    s.add_argument("tag")
    s.add_argument("value", type=float)
    s = sub.add_parser("fault")
    s.add_argument("device")
    s.add_argument("kind")
    s.add_argument("params", nargs="?", default="{}")
    s = sub.add_parser("clear-faults")
    s.add_argument("device")

    a = p.parse_args(argv)
    setup_logging(a.log_level)
    cfg = load_config(a.config)

    with contextlib.suppress(KeyboardInterrupt):
        match a.cmd:
            case "sim":
                from factory_control.plc.runner import load_scenario, run_simulator

                asyncio.run(run_simulator(cfg, load_scenario(a.scenario)))
            case "supervisor":
                from factory_control.supervisor.app import run_supervisor

                asyncio.run(run_supervisor(cfg))
            case "dashboard":
                import uvicorn

                from factory_control.dashboard.app import create_app

                uvicorn.run(create_app(cfg), host=cfg.dashboard.host, port=cfg.dashboard.port)
            case "write":
                asyncio.run(write_tag(cfg, a.device, a.tag, a.value))
            case "fault":
                json.loads(a.params)  # validate before sending
                asyncio.run(_sim_method(cfg, a.device, "InjectFault", a.kind, a.params))
            case "clear-faults":
                asyncio.run(_sim_method(cfg, a.device, "ClearFaults"))


if __name__ == "__main__":
    main()

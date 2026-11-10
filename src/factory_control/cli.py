"""Command-line entry point: ``fc <command>``.

fc sim [--scenario FILE]       run the simulated line (both OPC UA servers)
fc supervisor                  run clients + historian + analyzer + controller
fc dashboard                   serve the web dashboard
fc setpoint MACHINE RPM        write a speed setpoint directly to a machine
fc fault MACHINE KIND [JSON]   inject a fault (simulator only)
fc clear-faults MACHINE        clear all injected faults (simulator only)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from pathlib import Path

from factory_control.common import tags as T
from factory_control.common.logging import setup_logging
from factory_control.config import DEFAULT_CONFIG_PATH, AppConfig, load_config


async def _with_machine(cfg: AppConfig, machine_id: str, fn):  # noqa: ANN001, ANN202
    from asyncua import Client

    client = Client(cfg.machine(machine_id).opcua.endpoint, timeout=4)
    client.session_timeout = 30_000
    async with client:
        return await fn(client)


async def _setpoint(cfg: AppConfig, machine_id: str, rpm: float) -> None:
    from asyncua import ua

    async def go(client):  # noqa: ANN001, ANN202
        ns = await client.get_namespace_index(T.FEEDER_NS_URI)
        path = [f"{ns}:{T.ROOT_OBJECT}", *(f"{ns}:{p}" for p in T.SPEED_SETPOINT.path)]
        node = await client.nodes.objects.get_child(path)
        await node.write_value(ua.Variant(rpm, ua.VariantType.Double))

    await _with_machine(cfg, machine_id, go)
    print(f"{machine_id}: setpoint {rpm} rpm written")


async def _sim_method(cfg: AppConfig, machine_id: str, method: str, *args: str) -> None:
    async def go(client):  # noqa: ANN001, ANN202
        ns = await client.get_namespace_index(T.SIM_NS_URI)
        sim = await client.nodes.objects.get_child([f"{ns}:{T.SIM_OBJECT}"])
        return await sim.call_method(f"{ns}:{method}", *args)

    print(f"{machine_id}: {method} -> {await _with_machine(cfg, machine_id, go)}")


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
    s = sub.add_parser("setpoint")
    s.add_argument("machine")
    s.add_argument("rpm", type=float)
    s = sub.add_parser("fault")
    s.add_argument("machine")
    s.add_argument("kind")
    s.add_argument("params", nargs="?", default="{}")
    s = sub.add_parser("clear-faults")
    s.add_argument("machine")

    a = p.parse_args(argv)
    setup_logging(a.log_level)
    cfg = load_config(a.config)

    with contextlib.suppress(KeyboardInterrupt):
        match a.cmd:
            case "sim":
                from factory_control.machine.runner import load_scenario, run_simulator

                asyncio.run(run_simulator(cfg, load_scenario(a.scenario)))
            case "supervisor":
                from factory_control.supervisor.app import run_supervisor

                asyncio.run(run_supervisor(cfg))
            case "dashboard":
                import uvicorn

                from factory_control.dashboard.app import create_app

                uvicorn.run(create_app(cfg), host=cfg.dashboard.host, port=cfg.dashboard.port)
            case "setpoint":
                asyncio.run(_setpoint(cfg, a.machine, a.rpm))
            case "fault":
                json.loads(a.params)  # validate before sending
                asyncio.run(_sim_method(cfg, a.machine, "InjectFault", a.kind, a.params))
            case "clear-faults":
                asyncio.run(_sim_method(cfg, a.machine, "ClearFaults"))


if __name__ == "__main__":
    main()

"""Generic device PLC: OPC UA server + scan cycle.

The address space is generated from ``common.tags`` for the device's type and
fitted instruments, so PLC and supervisor cannot disagree about it. See
docs/opcua.md for variables vs. methods, timestamps and namespaces.

Scan cycle (called every physics step by the runner):
  1. ``apply_client_writes``: pick up setpoints written by an OPC UA client
  2. ``local_logic``: device-specific control (overridden by subclasses)
Publishing happens at the slower publish period (``publish``).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from asyncua import Node, Server, ua, uamethod

from factory_control.common import tags as T
from factory_control.sim.clock import SimClock
from factory_control.sim.devices.base import DevicePlant
from factory_control.sim.faults import FaultKind

log = logging.getLogger(__name__)

_VARIANT = {
    T.ValueType.DOUBLE: ua.VariantType.Double,
    T.ValueType.BOOLEAN: ua.VariantType.Boolean,
    T.ValueType.STRING: ua.VariantType.String,
    T.ValueType.DOUBLE_ARRAY: ua.VariantType.Double,
    T.ValueType.BOOLEAN_ARRAY: ua.VariantType.Boolean,
}
_INITIAL = {
    T.ValueType.DOUBLE: 0.0,
    T.ValueType.BOOLEAN: False,
    T.ValueType.STRING: "",
    T.ValueType.DOUBLE_ARRAY: [0.0],
    T.ValueType.BOOLEAN_ARRAY: [False],
}


def _ts(unix_s: float) -> datetime:
    return datetime.fromtimestamp(unix_s, tz=UTC)


class DevicePLC:
    def __init__(self, cfg: Any, plant: DevicePlant, clock: SimClock) -> None:
        self.cfg = cfg
        self.plant = plant
        self.clock = clock
        self.tags = T.tags_for(cfg.type, cfg.instruments)
        self.root_name = T.DEVICE_TYPES[cfg.type].root
        self.server = Server()
        self.nodes: dict[str, Node] = {}
        self.params: dict[str, float] = {}  # last accepted value of each writable tag
        self.plc_values: dict[str, Any] = {}  # PLC-computed values to publish (e.g. PID output)

    # -- lifecycle ----------------------------------------------------------------------

    def initial_params(self) -> dict[str, float]:
        """Initial values of writable tags. Subclasses extend."""
        if self.plant.motor is not None:
            return {T.SPEED_SETPOINT.key: self.plant.motor.state.setpoint_rpm}
        return {}

    async def init(self) -> None:
        s = self.server
        await s.init()
        s.set_endpoint(self.cfg.opcua.endpoint)
        s.set_server_name(f"factory-control {self.cfg.id}")
        # D-12: no security while developing on localhost. Must change before any real network.
        s.set_security_policy([ua.SecurityPolicyType.NoSecurity])

        ns = await s.register_namespace(T.DEVICE_NS_URI)
        root = await s.nodes.objects.add_object(ns, self.root_name)
        folders: dict[tuple[str, ...], Node] = {}
        for tag in self.tags:
            parent = root
            for i in range(1, len(tag.path)):
                key = tag.path[:i]
                if key not in folders:
                    folders[key] = await parent.add_object(ns, tag.path[i - 1])
                parent = folders[key]
            node = await parent.add_variable(
                ns, tag.path[-1], _INITIAL[tag.vtype], varianttype=_VARIANT[tag.vtype]
            )
            if tag.writable:
                await node.set_writable()
            self.nodes[tag.key] = node

        now = self.clock.now
        await self._write(T.DEVICE_ID, self.cfg.id, now)
        if T.VIB_SAMPLE_RATE in self.tags:
            await self._write(T.VIB_SAMPLE_RATE, self.cfg.vibration.sample_rate_hz, now)
        self.params = self.initial_params()
        for key, value in self.params.items():
            await self._write(T.ALL_TAGS[key], value, now)
        await self._build_simulation_object()

    async def start(self) -> None:
        await self.server.start()
        log.info("%s PLC serving at %s", self.cfg.id, self.cfg.opcua.endpoint)

    async def stop(self) -> None:
        await self.server.stop()

    # -- sim-only object (D-14) ---------------------------------------------------------

    async def _build_simulation_object(self) -> None:
        ns = await self.server.register_namespace(T.SIM_NS_URI)
        sim = await self.server.nodes.objects.add_object(ns, T.SIM_OBJECT)
        self.nodes["sim.active_faults"] = await sim.add_variable(ns, "ActiveFaults", "{}")
        faults = self.plant.faults

        @uamethod
        def inject_fault(_parent: ua.NodeId, name: str, params_json: str) -> bool:
            faults.inject(FaultKind(name), json.loads(params_json or "{}"))
            log.warning("%s: fault injected %s %s", self.cfg.id, name, params_json)
            return True

        @uamethod
        def clear_faults(_parent: ua.NodeId) -> bool:
            faults.clear()
            log.warning("%s: faults cleared", self.cfg.id)
            return True

        await sim.add_method(
            ns, "InjectFault", inject_fault,
            [ua.VariantType.String, ua.VariantType.String], [ua.VariantType.Boolean],
        )  # fmt: skip
        await sim.add_method(ns, "ClearFaults", clear_faults, [], [ua.VariantType.Boolean])

    # -- scan cycle ---------------------------------------------------------------------

    def apply_client_writes(self) -> None:
        """Pick up changed writable tags. A direct attribute read is an in-memory lookup.

        TODO(D-13): validation of out-of-range writes.
        """
        for key in self.params:
            dv = self.server.read_attribute_value(self.nodes[key].nodeid)
            value = float(dv.Value.Value)
            if value != self.params[key]:
                self.params[key] = value
                self.on_write(key, value)

    def on_write(self, key: str, value: float) -> None:
        if key == T.SPEED_SETPOINT.key and self.plant.motor is not None:
            self.plant.motor.command(value)

    def local_logic(self, dt: float) -> None:
        """Device-specific control executed every scan. Default: none."""
        del dt

    # -- publishing ---------------------------------------------------------------------

    async def publish(self, now: float) -> None:
        for key, value in {**self.plant.measure(), **self.plc_values}.items():
            await self._write(T.ALL_TAGS[key], value, now)
        active = {k.value: v for k, v in self.plant.faults.active.items()}
        await self.server.write_attribute_value(
            self.nodes["sim.active_faults"].nodeid,
            ua.DataValue(ua.Variant(json.dumps(active), ua.VariantType.String),
                         SourceTimestamp=_ts(now), ServerTimestamp=_ts(now)),
        )  # fmt: skip

    async def publish_vibration(self, now: float) -> float | None:
        """Publish one vibration block if the device has a sensor; returns its duration."""
        block = self.plant.vibration_block()
        if block is None or T.VIB_WAVEFORM not in self.tags:
            return None
        await self._write(T.VIB_WAVEFORM, block.tolist(), now)
        return self.cfg.vibration.block_size / self.cfg.vibration.sample_rate_hz

    async def _write(self, tag: T.Tag, value: object, now: float) -> None:
        dv = ua.DataValue(
            ua.Variant(value, _VARIANT[tag.vtype]),
            SourceTimestamp=_ts(now),
            ServerTimestamp=datetime.now(UTC),
        )
        await self.server.write_attribute_value(self.nodes[tag.key].nodeid, dv)

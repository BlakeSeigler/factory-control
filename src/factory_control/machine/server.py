"""OPC UA server for one feeder.

The address space is generated from ``common.tags.FEEDER_TAGS`` so the server and
the supervisor's client cannot disagree about it. See docs/opcua.md for the
reasoning behind variables-vs-methods, timestamps and namespaces.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from asyncua import Node, Server, ua, uamethod

from factory_control.common import tags as T
from factory_control.config import MachineConfig
from factory_control.sim.clock import SimClock
from factory_control.sim.faults import FaultKind
from factory_control.sim.feeder import Feeder

log = logging.getLogger(__name__)

_VARIANT = {
    T.ValueType.DOUBLE: ua.VariantType.Double,
    T.ValueType.BOOLEAN: ua.VariantType.Boolean,
    T.ValueType.STRING: ua.VariantType.String,
    T.ValueType.DOUBLE_ARRAY: ua.VariantType.Double,
}
_INITIAL = {
    T.ValueType.DOUBLE: 0.0,
    T.ValueType.BOOLEAN: False,
    T.ValueType.STRING: "",
    T.ValueType.DOUBLE_ARRAY: [0.0],
}


def _ts(unix_s: float) -> datetime:
    return datetime.fromtimestamp(unix_s, tz=UTC)


class FeederServer:
    def __init__(self, cfg: MachineConfig, feeder: Feeder, clock: SimClock) -> None:
        self.cfg = cfg
        self.feeder = feeder
        self.clock = clock
        self.server = Server()
        self.nodes: dict[str, Node] = {}
        self._last_setpoint: float | None = None

    # -- lifecycle ----------------------------------------------------------------------

    async def init(self) -> None:
        s = self.server
        await s.init()
        s.set_endpoint(self.cfg.opcua.endpoint)
        s.set_server_name(f"factory-control {self.cfg.id}")
        # D-08: no security while developing on localhost. Must change before any real network.
        s.set_security_policy([ua.SecurityPolicyType.NoSecurity])

        ns = await s.register_namespace(T.FEEDER_NS_URI)
        root = await s.nodes.objects.add_object(ns, T.ROOT_OBJECT)
        folders: dict[tuple[str, ...], Node] = {}
        for tag in T.tags_for(self.cfg.instruments):
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

        await self._write(T.MACHINE_ID, self.cfg.id, self.clock.now)
        await self._write(T.VIB_SAMPLE_RATE, self.cfg.vibration.sample_rate_hz, self.clock.now)
        await self._write(T.SPEED_SETPOINT, self.feeder.motor.state.setpoint_rpm, self.clock.now)
        self._last_setpoint = self.feeder.motor.state.setpoint_rpm
        await self._build_simulation_object()

    async def start(self) -> None:
        await self.server.start()
        log.info("%s serving at %s", self.cfg.id, self.cfg.opcua.endpoint)

    async def stop(self) -> None:
        await self.server.stop()

    # -- sim-only object (D-12) ---------------------------------------------------------

    async def _build_simulation_object(self) -> None:
        ns = await self.server.register_namespace(T.SIM_NS_URI)
        sim = await self.server.nodes.objects.add_object(ns, T.SIM_OBJECT)
        self.nodes["sim.active_faults"] = await sim.add_variable(ns, "ActiveFaults", "{}")

        faults = self.feeder.faults

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
            ns,
            "InjectFault",
            inject_fault,
            [ua.VariantType.String, ua.VariantType.String],
            [ua.VariantType.Boolean],
        )
        await sim.add_method(ns, "ClearFaults", clear_faults, [], [ua.VariantType.Boolean])

    # -- cyclic I/O ---------------------------------------------------------------------

    def apply_client_writes(self) -> None:
        """Pull the SpeedSetpoint node into the plant if a client changed it.

        Polled every physics step; a direct attribute read is an in-memory lookup.
        TODO(D-09): replace with a write setter that rejects out-of-range values
        with BadOutOfRange instead of silently clamping.
        """
        dv = self.server.read_attribute_value(self.nodes[T.SPEED_SETPOINT.key].nodeid)
        requested = float(dv.Value.Value)
        if requested != self._last_setpoint:
            applied = self.feeder.command_speed(requested)
            self._last_setpoint = requested
            if applied != requested:
                log.warning("%s: setpoint %.1f clamped to %.1f", self.cfg.id, requested, applied)

    async def publish(self, now: float) -> None:
        m = self.feeder.measure()
        await self._write(T.SPEED, m.speed_rpm, now)
        await self._write(T.MOTOR_TEMP, m.temperature_c, now)
        await self._write(T.MOTOR_CURRENT, m.current_a, now)
        await self._write(T.LEVEL_LOW, m.level_low, now)
        await self._write(T.LEVEL_HIGH, m.level_high, now)
        if m.hopper_weight_kg is not None:
            await self._write(T.HOPPER_WEIGHT, m.hopper_weight_kg, now)
        active = {k.value: v for k, v in self.feeder.faults.active.items()}
        await self.server.write_attribute_value(
            self.nodes["sim.active_faults"].nodeid,
            ua.DataValue(
                ua.Variant(json.dumps(active), ua.VariantType.String),
                SourceTimestamp=_ts(now),
                ServerTimestamp=_ts(now),
            ),
        )

    async def publish_vibration(self, block: list[float], block_start: float) -> None:
        await self._write(T.VIB_WAVEFORM, block, block_start)

    async def _write(self, tag: T.Tag, value: object, now: float) -> None:
        dv = ua.DataValue(
            ua.Variant(value, _VARIANT[tag.vtype]),
            SourceTimestamp=_ts(now),
            ServerTimestamp=datetime.now(UTC),
        )
        await self.server.write_attribute_value(self.nodes[tag.key].nodeid, dv)

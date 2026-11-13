"""Generic device PLC: hosts the device's OPC UA server and runs its scan cycle.

The address space is generated from the device type's tags (common/tags.py), so
PLC and supervisor cannot disagree about it (docs/opcua.md).

Setpoints: every writable tag must have a ``Setpoint`` (initial value, allowed
range, and what applying it does). Writes are validated at the OPC UA boundary: an
out-of-range write is rejected with ``BadOutOfRange``, which the writing client
receives as an error (D-13).

Scan cycle: the runner calls ``scan`` every physics step (device logic, overridden
by subclasses) and ``publish`` every publish period.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from asyncua import Node, Server, ua, uamethod
from asyncua.server.address_space import NodeData

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
}
_INITIAL = {
    T.ValueType.DOUBLE: 0.0,
    T.ValueType.BOOLEAN: False,
    T.ValueType.STRING: "",
    T.ValueType.DOUBLE_ARRAY: [0.0],
}


@dataclass(frozen=True, slots=True)
class Setpoint:
    initial: float
    low: float
    high: float
    apply: Callable[[float], None]  # hands an accepted value to the plant or PLC logic


class DevicePLC:
    def __init__(self, cfg: Any, plant: DevicePlant, clock: SimClock) -> None:
        self.cfg = cfg
        self.plant = plant
        self.clock = clock
        self.tags = cfg.tags
        self.server = Server()
        self.nodes: dict[str, Node] = {}

    # -- device-specific hooks ----------------------------------------------------------

    def setpoints(self) -> dict[str, Setpoint]:
        """One entry per writable tag. Default: the drive's speed, if there is one."""
        if self.plant.drive is None:
            return {}
        m = self.cfg.motor
        return {
            T.SPEED_SETPOINT.key: Setpoint(
                m.initial_rpm, m.min_rpm, m.max_rpm, self.plant.drive.motor.command
            )
        }

    def scan(self, dt: float) -> None:
        """Device logic executed every physics step. Default: none."""
        del dt

    # -- lifecycle ----------------------------------------------------------------------

    async def init(self) -> None:
        s = self.server
        await s.init()
        s.set_endpoint(self.cfg.opcua.endpoint)
        s.set_server_name(f"factory-control {self.cfg.id}")
        # D-12: no security while developing on localhost. Must change before any real network.
        s.set_security_policy([ua.SecurityPolicyType.NoSecurity])

        ns = await s.register_namespace(T.DEVICE_NS_URI)
        root = await s.nodes.objects.add_object(ns, T.DEVICE_TYPES[self.cfg.type].root)
        folders: dict[tuple[str, ...], Node] = {}
        for tag in self.tags:
            parent = root
            for i in range(1, len(tag.path)):
                if tag.path[:i] not in folders:
                    folders[tag.path[:i]] = await parent.add_object(ns, tag.path[i - 1])
                parent = folders[tag.path[:i]]
            self.nodes[tag.key] = await parent.add_variable(
                ns, tag.path[-1], _INITIAL[tag.vtype], varianttype=_VARIANT[tag.vtype]
            )

        await self._init_setpoints()
        now = self.clock.now
        for key, value in {T.DEVICE_ID.key: self.cfg.id, **self.plant.constants()}.items():
            await self._write(key, value, now)
        await self._build_simulation_object()

    async def start(self) -> None:
        await self.server.start()
        log.info("%s PLC serving at %s", self.cfg.id, self.cfg.opcua.endpoint)

    async def stop(self) -> None:
        await self.server.stop()

    # -- setpoints (D-13) ---------------------------------------------------------------

    async def _init_setpoints(self) -> None:
        specs = self.setpoints()
        writable = {t.key for t in self.tags if t.writable}
        if set(specs) != writable:
            raise TypeError(
                f"{self.cfg.id}: setpoints {sorted(specs)} != writable {sorted(writable)}"
            )
        for key, spec in specs.items():
            node = self.nodes[key]
            await node.set_writable()
            self.server.set_attribute_value_setter(
                node.nodeid, functools.partial(self._accept_write, key, spec)
            )
            await self._write(key, spec.initial, self.clock.now)  # validated like any write

    def _accept_write(
        self, key: str, spec: Setpoint, node: NodeData, attr: ua.AttributeIds, dv: ua.DataValue
    ) -> None:
        value = float(dv.Value.Value)
        if not spec.low <= value <= spec.high:
            log.warning("%s: rejected %s = %g (allowed %g..%g)", self.cfg.id, key, value,
                        spec.low, spec.high)  # fmt: skip
            raise ua.uaerrors.BadOutOfRange()
        node.attributes[attr].value = dv
        spec.apply(value)

    # -- sim-only object (D-14) ---------------------------------------------------------

    async def _build_simulation_object(self) -> None:
        ns = await self.server.register_namespace(T.SIM_NS_URI)
        sim = await self.server.nodes.objects.add_object(ns, T.SIM_OBJECT)
        self.nodes[T.GROUND_TRUTH_KEY] = await sim.add_variable(ns, T.SIM_ACTIVE_FAULTS, "{}")
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
            ns, T.SIM_INJECT_FAULT, inject_fault,
            [ua.VariantType.String, ua.VariantType.String], [ua.VariantType.Boolean],
        )  # fmt: skip
        await sim.add_method(ns, T.SIM_CLEAR_FAULTS, clear_faults, [], [ua.VariantType.Boolean])

    # -- publishing ---------------------------------------------------------------------

    async def publish(self, now: float) -> None:
        for key, value in self.plant.measure().items():
            await self._write(key, value, now)
        active = {k.value: v for k, v in self.plant.faults.active.items()}
        await self._write(T.GROUND_TRUTH_KEY, json.dumps(active), now)

    async def publish_vibration(self, now: float) -> float | None:
        """Publish one vibration block if the device has a sensor; returns its duration."""
        block = self.plant.vibration_block()
        if block is None:
            return None
        await self._write(T.VIB_WAVEFORM.key, block.tolist(), now)
        return self.plant.vibration.block_duration_s  # type: ignore[union-attr]

    async def _write(self, key: str, value: Any, now: float) -> None:
        tag = T.ALL_TAGS.get(key)
        vtype = _VARIANT[tag.vtype] if tag else ua.VariantType.String  # ground truth: JSON
        dv = ua.DataValue(
            ua.Variant(value, vtype),
            SourceTimestamp=datetime.fromtimestamp(now, tz=UTC),
            ServerTimestamp=datetime.now(UTC),
        )
        await self.server.write_attribute_value(self.nodes[key].nodeid, dv)

"""Simulated PLCs: one per device, each hosting that device's OPC UA server.

A PLC sits between the supervisor and its device's plant model, as on real
equipment: it receives setpoints over OPC UA, runs local control (barrel PID,
interlocks) every scan, drives the plant's actuators, and publishes sensor values.
"""

from __future__ import annotations

from factory_control.config import DeviceConfig
from factory_control.plc.base import DevicePLC
from factory_control.plc.extruder import ExtruderPLC
from factory_control.plc.shredder import ShredderPLC
from factory_control.sim.clock import SimClock
from factory_control.sim.devices.base import DevicePlant

_PLCS: dict[str, type[DevicePLC]] = {"extruder": ExtruderPLC, "shredder": ShredderPLC}


def build_plc(cfg: DeviceConfig, plant: DevicePlant, clock: SimClock) -> DevicePLC:
    return _PLCS.get(cfg.type, DevicePLC)(cfg, plant, clock)

"""Extruder PLC.

NOT IMPLEMENTED:
  * barrel temperature loop: thermocouple -> PID (plc/pid.py) -> heater duty (D-26)
  * cold-start interlock: hold the screw at 0 rpm below min_screw_temp_c (D-28)
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.config import ExtruderDeviceConfig
from factory_control.plc.base import DevicePLC


class ExtruderPLC(DevicePLC):
    cfg: ExtruderDeviceConfig

    def initial_params(self) -> dict[str, float]:
        return {**super().initial_params(), T.BARREL_SETPOINT.key: self.cfg.barrel.setpoint_c}

    def on_write(self, key: str, value: float) -> None:
        if key == T.BARREL_SETPOINT.key:
            return  # TODO(D-26): hand the setpoint to the barrel PID
        super().on_write(key, value)

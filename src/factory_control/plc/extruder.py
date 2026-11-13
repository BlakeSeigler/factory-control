"""Extruder PLC.

NOT IMPLEMENTED:
  * barrel temperature loop: barrel thermocouple -> PID (plc/pid.py) -> heater duty,
    publishing the PID output as Barrel/HeaterOutput (D-26)
  * cold-start interlock: hold the screw at 0 rpm below a minimum barrel
    temperature (D-28)
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.config import ExtruderConfig
from factory_control.plc.base import DevicePLC, Setpoint


class ExtruderPLC(DevicePLC):
    cfg: ExtruderConfig

    def setpoints(self) -> dict[str, Setpoint]:
        b = self.cfg.barrel
        return {
            **super().setpoints(),
            T.BARREL_SETPOINT.key: Setpoint(
                b.setpoint_c, b.min_setpoint_c, b.max_setpoint_c, self._set_barrel_setpoint
            ),
        }

    def _set_barrel_setpoint(self, value_c: float) -> None:
        self.barrel_setpoint_c = value_c  # TODO(D-26): hand to the barrel PID

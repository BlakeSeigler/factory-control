"""Extruder PLC: barrel temperature PID and the cold-start interlock."""

from __future__ import annotations

import logging

from factory_control.common import tags as T
from factory_control.config import ExtruderDeviceConfig
from factory_control.plc.base import DevicePLC
from factory_control.plc.pid import Pid
from factory_control.sim.devices.extruder import ExtruderPlant

log = logging.getLogger(__name__)


class ExtruderPLC(DevicePLC):
    cfg: ExtruderDeviceConfig
    plant: ExtruderPlant

    def __init__(self, cfg, plant, clock) -> None:  # noqa: ANN001
        super().__init__(cfg, plant, clock)
        self.barrel_pid = Pid(cfg.barrel.pid, setpoint=cfg.barrel.setpoint_c)

    def initial_params(self) -> dict[str, float]:
        return {**super().initial_params(), T.BARREL_SETPOINT.key: self.cfg.barrel.setpoint_c}

    def on_write(self, key: str, value: float) -> None:
        if key == T.BARREL_SETPOINT.key:
            applied = min(value, self.cfg.barrel.max_setpoint_c)
            if applied != value:
                log.warning("%s: barrel setpoint %.1f clamped to %.1f", self.cfg.id, value, applied)
            self.barrel_pid.setpoint = applied
            return
        super().on_write(key, value)

    def local_logic(self, dt: float) -> None:
        # Barrel temperature loop: thermocouple -> PID -> heater duty.
        # TODO(D-26): time-proportioning (heater SSR on/off within a cycle) and tuning.
        pv = self.plant.measure()[T.BARREL_TEMP.key]
        duty = self.barrel_pid.update(pv, dt)
        self.plant.set_heater(duty)
        self.plc_values[T.HEATER_OUTPUT.key] = duty

        # TODO(D-28): cold-start interlock. Below min_screw_temp_c the PLC must hold
        # the screw at 0 rpm regardless of the setpoint (unmelted plastic can break a
        # screw). Not enabled yet because the barrel thermal model is a placeholder
        # that never heats up, which would keep the screw stopped forever.

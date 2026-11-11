"""Drive + motor (used by shredder, extruder, pelletizer).

NOT IMPLEMENTED. Model options: docs/plant-model.md section 2.1, D-15.

PLACEHOLDER so the infrastructure has something to carry: speed equals the
setpoint immediately. There is no dynamics, load, or current.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import MotorConfig


@dataclass(slots=True)
class MotorState:
    speed_rpm: float
    setpoint_rpm: float
    current_a: float = 0.0  # PLACEHOLDER (D-15)


class Motor:
    def __init__(self, cfg: MotorConfig) -> None:
        self.cfg = cfg
        self.state = MotorState(speed_rpm=cfg.initial_rpm, setpoint_rpm=cfg.initial_rpm)

    def command(self, setpoint_rpm: float) -> None:
        """Speed command to the drive. Limits/validation: D-13."""
        self.state.setpoint_rpm = setpoint_rpm

    def step(self, dt: float, load_torque_nm: float = 0.0) -> None:
        del dt, load_torque_nm  # PLACEHOLDER (D-15)
        self.state.speed_rpm = self.state.setpoint_rpm

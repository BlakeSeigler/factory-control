"""Motor temperature (shredder, extruder and pelletizer motors).

NOT IMPLEMENTED. Candidate: lumped model (docs/plant-model.md section 2.2, D-23)

    C_th * dT/dt = P_loss(I, omega) - (T - T_amb) / R_th(omega)
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import MotorThermalConfig


@dataclass(slots=True)
class MotorThermalState:
    temperature_c: float


class MotorThermal:
    def __init__(self, cfg: MotorThermalConfig) -> None:
        self.cfg = cfg
        self.state = MotorThermalState(temperature_c=cfg.initial_c)

    def step(self, dt: float, motor_speed_rpm: float, current_a: float) -> None:
        del dt, motor_speed_rpm, current_a  # PLACEHOLDER: held at initial value

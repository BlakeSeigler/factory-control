"""Motor thermal model.

NOT IMPLEMENTED. Candidate: single-node lumped model (docs/plant-model.md section 5)

    C_th * dT/dt = P_loss(I, omega) - (T - T_amb) / R_th(omega)

with R_th speed-dependent for a shaft-mounted fan (TEFC motor) and faults acting
on P_loss (winding short, overload) or R_th (blocked fan). Whether we need a
two-node (winding + frame) model is D-15.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import ThermalConfig


@dataclass(slots=True)
class ThermalState:
    temperature_c: float


class MotorThermal:
    def __init__(self, cfg: ThermalConfig) -> None:
        self.cfg = cfg
        self.state = ThermalState(temperature_c=cfg.initial_c)

    def step(self, dt: float, motor_speed_rpm: float, load_torque_nm: float) -> None:
        # PLACEHOLDER: temperature held at its initial value.
        del dt, motor_speed_rpm, load_torque_nm

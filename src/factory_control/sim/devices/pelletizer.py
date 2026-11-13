"""Strand pelletizer: feed rolls pull the strands, a rotor with knives cuts them.

NOT IMPLEMENTED: pellet geometry, strand dynamics (draw-down, sag, breaks).
Equations and options: docs/plant-model.md section 3.5, D-10, D-19.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import MaterialConfig, PelletizerDeviceConfig
from factory_control.sim.components.motor import Motor
from factory_control.sim.components.motor_thermal import MotorThermal
from factory_control.sim.devices.base import DevicePlant


class PelletizerPlant(DevicePlant):
    cfg: PelletizerDeviceConfig

    def __init__(
        self, cfg: PelletizerDeviceConfig, material: MaterialConfig, rng: np.random.Generator
    ) -> None:
        super().__init__(cfg, material, rng)
        self.motor = Motor(cfg.motor)
        self.thermal = MotorThermal(cfg.motor_thermal)

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t  # PLACEHOLDER: material passes straight through
        self.motor.step(dt)
        self.thermal.step(dt, self.motor.state.speed_rpm, self.motor.state.current_a)
        return inflow_kg_s

    def measure(self) -> dict[str, Any]:
        return {
            T.SPEED.key: self.motor.state.speed_rpm,
            T.MOTOR_CURRENT.key: self.motor.state.current_a,
            T.MOTOR_TEMP.key: self.thermal.state.temperature_c,
        }

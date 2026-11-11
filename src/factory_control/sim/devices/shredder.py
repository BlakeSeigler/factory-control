"""Shredder unit: weighed infeed hopper + single rotor driven by a VFD motor.

Throughput model NOT IMPLEMENTED (docs/plant-model.md section 3.2, D-16).
Candidate: m_dot = min(material available to the rotor,
                       capacity(rotor rpm) * cutting efficiency(knife wear, faults)),
with a strongly fluctuating cutting torque (chunks, bale density), and jams when a
hard or oversized piece stalls the rotor.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import MaterialConfig, ShredderDeviceConfig
from factory_control.sim.components.hopper import Hopper
from factory_control.sim.components.motor import Motor
from factory_control.sim.components.motor_thermal import MotorThermal
from factory_control.sim.components.sensors import LevelSwitch, LoadCell
from factory_control.sim.components.vibration import VibrationSynth
from factory_control.sim.devices.base import DevicePlant


class ShredderPlant(DevicePlant):
    cfg: ShredderDeviceConfig

    def __init__(
        self, cfg: ShredderDeviceConfig, material: MaterialConfig, rng: np.random.Generator
    ) -> None:
        super().__init__(cfg, material, rng)
        self.hopper = Hopper(cfg.hopper)
        self.motor = Motor(cfg.motor)
        self.thermal = MotorThermal(cfg.motor_thermal)
        self.vibration = VibrationSynth(cfg.vibration, rng)
        self.low, self.high = (
            LevelSwitch(cfg.hopper.low_switch_kg),
            LevelSwitch(cfg.hopper.high_switch_kg),
        )
        self.load_cell = LoadCell(cfg.hopper.load_cell) if cfg.hopper.load_cell else None
        self.output_kg_s = 0.0

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        demand = 0.0  # PLACEHOLDER (D-16): rotor throughput as a function of speed
        self.output_kg_s = self.hopper.step(dt, inflow_kg_s, demand)
        self.motor.step(dt)
        self.thermal.step(dt, self.motor.state.speed_rpm, self.motor.state.current_a)
        return self.output_kg_s

    def measure(self) -> dict[str, Any]:
        m = self.hopper.state.mass_kg
        out: dict[str, Any] = {
            T.LEVEL_LOW.key: self.low.read(m),
            T.LEVEL_HIGH.key: self.high.read(m),
            T.SPEED.key: self.motor.state.speed_rpm,
            T.MOTOR_CURRENT.key: self.motor.state.current_a,
            T.MOTOR_TEMP.key: self.thermal.state.temperature_c,
        }
        if self.load_cell:
            out[T.HOPPER_WEIGHT.key] = self.load_cell.read(m)
        return out

    def vibration_block(self) -> np.ndarray:
        return self.vibration.next_block(self.motor.state.speed_rpm)

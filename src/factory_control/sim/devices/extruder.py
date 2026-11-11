"""Extruder unit: hopper + single screw (VFD motor through a gearbox) + heated barrel.

NOT IMPLEMENTED beyond the interface (docs/plant-model.md section 3.3, D-17, D-18):

  output     flood-fed: m_dot ~ k(N, die resistance, viscosity) * N_screw;
             starve-fed when the hopper runs empty
  barrel     C_b dT_b/dt = P_heater + P_shear - P_to_melt - P_loss
             (screw speed heats the melt by shear: the coupling between the
             screw-speed and barrel-temperature loops)
  heater     actuated by the PLC's barrel PID (``set_heater``), 0-100 % duty
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import ExtruderDeviceConfig, MaterialConfig
from factory_control.sim.components.hopper import Hopper
from factory_control.sim.components.motor import Motor
from factory_control.sim.components.motor_thermal import MotorThermal
from factory_control.sim.components.sensors import LevelSwitch, Thermocouple
from factory_control.sim.components.vibration import VibrationSynth
from factory_control.sim.devices.base import DevicePlant


class ExtruderPlant(DevicePlant):
    cfg: ExtruderDeviceConfig

    def __init__(
        self, cfg: ExtruderDeviceConfig, material: MaterialConfig, rng: np.random.Generator
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
        self.barrel_tc = Thermocouple()
        self.barrel_temp_c = cfg.barrel.initial_c
        self.heater_duty_pct = 0.0
        self.output_kg_s = 0.0

    # actuators -----------------------------------------------------------------------

    def set_heater(self, duty_pct: float) -> None:
        self.heater_duty_pct = min(max(duty_pct, 0.0), 100.0)

    # physics -------------------------------------------------------------------------

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        demand = 0.0  # PLACEHOLDER (D-17): screw output as a function of screw speed
        self.output_kg_s = self.hopper.step(dt, inflow_kg_s, demand)
        self.motor.step(dt)
        self.thermal.step(dt, self.motor.state.speed_rpm, self.motor.state.current_a)
        # PLACEHOLDER (D-18): barrel temperature held; heater duty has no effect yet.
        return self.output_kg_s

    def measure(self) -> dict[str, Any]:
        m = self.hopper.state.mass_kg
        return {
            T.LEVEL_LOW.key: self.low.read(m),
            T.LEVEL_HIGH.key: self.high.read(m),
            T.SPEED.key: self.motor.state.speed_rpm,
            T.MOTOR_CURRENT.key: self.motor.state.current_a,
            T.MOTOR_TEMP.key: self.thermal.state.temperature_c,
            T.BARREL_TEMP.key: self.barrel_tc.read(self.barrel_temp_c),
        }

    def vibration_block(self) -> np.ndarray:
        return self.vibration.next_block(self.motor.state.speed_rpm)

    def truth(self) -> dict[str, float]:
        return {"hopper_mass_kg": self.hopper.state.mass_kg, "output_kg_s": self.output_kg_s}

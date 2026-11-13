"""Extruder unit: hopper + single screw (VFD motor) + heated barrel + die.

NOT IMPLEMENTED (docs/plant-model.md section 3.3, D-17, D-18): screw output, barrel
heat balance with shear heating, melt temperature.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import ExtruderConfig
from factory_control.sim.components.drive import Drive
from factory_control.sim.components.hopper import Hopper
from factory_control.sim.components.sensors import HopperSwitches, Thermocouple
from factory_control.sim.components.vibration import VibrationSynth
from factory_control.sim.devices.base import DevicePlant


class ExtruderPlant(DevicePlant):
    cfg: ExtruderConfig

    def __init__(self, cfg: ExtruderConfig, rng: np.random.Generator) -> None:
        super().__init__(cfg, rng)
        self.hopper = Hopper(cfg.hopper)
        self.drive = Drive(cfg.motor, cfg.motor_thermal)
        self.vibration = VibrationSynth(cfg.vibration, rng)
        self.switches = HopperSwitches(cfg.hopper)
        self.barrel_temp_c = cfg.barrel.initial_c  # PLACEHOLDER (D-18): held constant
        self.melt_temp_c = cfg.barrel.initial_c  # PLACEHOLDER (D-18): held constant
        self.barrel_tc = Thermocouple()
        self.melt_tc = Thermocouple()
        self.heater_duty_pct = 0.0  # actuator, driven by the PLC's barrel PID (D-26)

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        demand = 0.0  # PLACEHOLDER (D-17): screw output
        self.drive.step(dt)
        return self.hopper.step(dt, inflow_kg_s, demand)

    def measure(self) -> dict[str, Any]:
        return {
            **self.switches.measure(self.hopper.state.mass_kg),
            **self.drive.measure(),
            T.BARREL_TEMP.key: self.barrel_tc.read(self.barrel_temp_c),
            T.MELT_TEMP.key: self.melt_tc.read(self.melt_temp_c),
        }

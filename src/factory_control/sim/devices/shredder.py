"""Shredder unit: weighed infeed hopper + single-shaft rotor driven by a VFD motor.

NOT IMPLEMENTED (docs/plant-model.md section 3.2, D-16): throughput as a function of
rotor speed and the hydraulic ram, the random cutting load, jams.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import ShredderConfig
from factory_control.sim.components.drive import Drive
from factory_control.sim.components.hopper import Hopper
from factory_control.sim.components.sensors import HopperSwitches, LoadCell
from factory_control.sim.components.vibration import VibrationSynth
from factory_control.sim.devices.base import DevicePlant


class ShredderPlant(DevicePlant):
    cfg: ShredderConfig

    def __init__(self, cfg: ShredderConfig, rng: np.random.Generator) -> None:
        super().__init__(cfg, rng)
        self.hopper = Hopper(cfg.hopper)
        self.drive = Drive(cfg.motor, cfg.motor_thermal)
        self.vibration = VibrationSynth(cfg.vibration, rng)
        self.switches = HopperSwitches(cfg.hopper)
        self.load_cell = LoadCell()

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        demand = 0.0  # PLACEHOLDER (D-16): rotor throughput
        self.drive.step(dt)
        return self.hopper.step(dt, inflow_kg_s, demand)

    def measure(self) -> dict[str, Any]:
        m = self.hopper.state.mass_kg
        return {
            **self.switches.measure(m),
            T.HOPPER_WEIGHT.key: self.load_cell.read(m),
            **self.drive.measure(),
        }

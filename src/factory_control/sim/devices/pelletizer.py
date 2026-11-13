"""Strand pelletizer: one motor drives the feed rolls and the knife rotor.

NOT IMPLEMENTED (docs/plant-model.md section 3.5, D-10, D-19): pellet geometry and
strand dynamics. Material passes straight through.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.config import PelletizerConfig
from factory_control.sim.components.drive import Drive
from factory_control.sim.devices.base import DevicePlant


class PelletizerPlant(DevicePlant):
    cfg: PelletizerConfig

    def __init__(self, cfg: PelletizerConfig, rng: np.random.Generator) -> None:
        super().__init__(cfg, rng)
        self.drive = Drive(cfg.motor, cfg.motor_thermal)

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        self.drive.step(dt)
        return inflow_kg_s

    def measure(self) -> dict[str, Any]:
        return self.drive.measure()

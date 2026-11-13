"""Water bath that cools and solidifies the strands. Sensor: water temperature.

NOT IMPLEMENTED (docs/plant-model.md section 3.4, D-20; deferred). Material passes
straight through.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import WaterBathConfig
from factory_control.sim.components.sensors import Thermocouple
from factory_control.sim.devices.base import DevicePlant


class WaterBathPlant(DevicePlant):
    cfg: WaterBathConfig

    def __init__(self, cfg: WaterBathConfig, rng: np.random.Generator) -> None:
        super().__init__(cfg, rng)
        self.water_temp_c = cfg.bath.initial_c  # PLACEHOLDER: held constant
        self.water_tc = Thermocouple()

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t, dt
        return inflow_kg_s

    def measure(self) -> dict[str, Any]:
        return {T.BATH_TEMP.key: self.water_tc.read(self.water_temp_c)}

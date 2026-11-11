"""Water bath that cools and solidifies the strands. Sensor: water temperature only.

NOT IMPLEMENTED (docs/plant-model.md section 3.4, D-20). Candidate heat balance:

    C_w dT_w/dt = m_dot * (cp * (T_melt - T_strand_out) + latent)    heat from strands
                  - m_dot_water * cp_w * (T_w - T_supply)             make-up / chiller
                  - UA * (T_w - T_amb)                                 losses

Material passes straight through (strands in transit are not a buffer worth modeling
yet).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import MaterialConfig, WaterBathDeviceConfig
from factory_control.sim.components.sensors import Thermocouple
from factory_control.sim.devices.base import DevicePlant


class WaterBathPlant(DevicePlant):
    cfg: WaterBathDeviceConfig

    def __init__(
        self, cfg: WaterBathDeviceConfig, material: MaterialConfig, rng: np.random.Generator
    ) -> None:
        super().__init__(cfg, material, rng)
        self.water_temp_c = cfg.bath.initial_c
        self.sensor = Thermocouple()

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t, dt  # PLACEHOLDER: water temperature held
        return inflow_kg_s

    def measure(self) -> dict[str, Any]:
        return {T.BATH_TEMP.key: self.sensor.read(self.water_temp_c)}

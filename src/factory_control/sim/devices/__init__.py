"""One plant model per device type. Construct via ``build_plant``."""

from __future__ import annotations

import numpy as np

from factory_control.config import DeviceConfig
from factory_control.sim.devices.base import DevicePlant
from factory_control.sim.devices.extruder import ExtruderPlant
from factory_control.sim.devices.pelletizer import PelletizerPlant
from factory_control.sim.devices.shredder import ShredderPlant
from factory_control.sim.devices.water_bath import WaterBathPlant

PLANTS: dict[str, type[DevicePlant]] = {
    "shredder": ShredderPlant,
    "extruder": ExtruderPlant,
    "water_bath": WaterBathPlant,
    "pelletizer": PelletizerPlant,
}


def build_plant(cfg: DeviceConfig, rng: np.random.Generator) -> DevicePlant:
    return PLANTS[cfg.type](cfg, rng)  # type: ignore[arg-type]

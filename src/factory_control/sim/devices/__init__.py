"""One plant model per device type. Construct via ``build_device``."""

from __future__ import annotations

import numpy as np

from factory_control.config import DeviceConfig, MaterialConfig
from factory_control.sim.devices.base import DevicePlant
from factory_control.sim.devices.extruder import ExtruderPlant
from factory_control.sim.devices.pelletizer import PelletizerPlant
from factory_control.sim.devices.shredder import ShredderPlant
from factory_control.sim.devices.water_bath import WaterBathPlant

_PLANTS: dict[str, type[DevicePlant]] = {
    "shredder": ShredderPlant,
    "extruder": ExtruderPlant,
    "water_bath": WaterBathPlant,
    "pelletizer": PelletizerPlant,
}


def build_device(
    cfg: DeviceConfig, material: MaterialConfig, rng: np.random.Generator
) -> DevicePlant:
    return _PLANTS[cfg.type](cfg, material, rng)  # type: ignore[arg-type]

"""Common shape of a device's plant model.

A plant has actuators (methods called by its PLC) and sensors (``measure``). It
contains no control logic; that is the PLC's job (plc/).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from factory_control.config import MaterialConfig
from factory_control.sim.components.motor import Motor
from factory_control.sim.faults import FaultManager


class DevicePlant(ABC):
    motor: Motor | None = None  # set by devices that have a drive

    def __init__(self, cfg: Any, material: MaterialConfig, rng: np.random.Generator) -> None:
        self.cfg = cfg
        self.id: str = cfg.id
        self.material = material
        self.rng = rng
        self.faults = FaultManager()

    @abstractmethod
    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        """Advance one physics step. ``inflow`` is material arriving from upstream;
        returns material leaving to downstream (kg/s)."""

    @abstractmethod
    def measure(self) -> dict[str, Any]:
        """Physical sensor readings keyed by tag key (common/tags.py)."""

    def vibration_block(self) -> np.ndarray | None:
        return None

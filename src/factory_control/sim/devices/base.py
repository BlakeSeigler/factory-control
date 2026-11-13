"""Common shape of a device's plant model.

A plant has actuators (attributes/methods its PLC drives) and sensors
(``measure``). It contains no control logic; that is the PLC's job (plc/).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.sim.components.drive import Drive
from factory_control.sim.components.vibration import VibrationSynth
from factory_control.sim.faults import FaultManager


class DevicePlant(ABC):
    drive: Drive | None = None  # motorized devices
    vibration: VibrationSynth | None = None  # devices with an accelerometer

    def __init__(self, cfg: Any, rng: np.random.Generator) -> None:
        self.cfg = cfg
        self.id: str = cfg.id
        self.rng = rng
        self.faults = FaultManager()

    @abstractmethod
    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        """Advance one physics step. ``inflow`` is material arriving from upstream;
        returns material leaving to downstream (kg/s)."""

    @abstractmethod
    def measure(self) -> dict[str, Any]:
        """Sensor readings keyed by tag key (common/tags.py)."""

    def constants(self) -> dict[str, Any]:
        """Values published once at start-up (e.g. sensor sample rates)."""
        if self.vibration is None:
            return {}
        return {T.VIB_SAMPLE_RATE.key: self.vibration.cfg.sample_rate_hz}

    def vibration_block(self) -> np.ndarray | None:
        if self.vibration is None or self.drive is None:
            return None
        return self.vibration.next_block(self.drive.motor.state.speed_rpm)

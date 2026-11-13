"""Measurement layer: true physical state -> what instruments report (D-22).

NOT IMPLEMENTED. Sensor models (noise, quantization, lag, hysteresis, faults) are
to be designed (docs/plant-model.md section 2.4). PLACEHOLDERS pass values through.
"""

from __future__ import annotations

from typing import Any

from factory_control.common import tags as T
from factory_control.config import HopperConfig


class LevelSwitch:
    """Point level switch. PLACEHOLDER: ideal threshold."""

    def __init__(self, threshold_kg: float) -> None:
        self.threshold_kg = threshold_kg

    def read(self, mass_kg: float) -> bool:
        return mass_kg >= self.threshold_kg


class HopperSwitches:
    """The low and high level switches of one hopper."""

    def __init__(self, cfg: HopperConfig) -> None:
        self.low = LevelSwitch(cfg.low_switch_kg)
        self.high = LevelSwitch(cfg.high_switch_kg)

    def measure(self, mass_kg: float) -> dict[str, Any]:
        return {T.LEVEL_LOW.key: self.low.read(mass_kg), T.LEVEL_HIGH.key: self.high.read(mass_kg)}


class LoadCell:
    """Hopper weighing (D-21). PLACEHOLDER: passes the true mass through."""

    def read(self, mass_kg: float) -> float:
        return mass_kg


class Thermocouple:
    """Temperature sensor. PLACEHOLDER: passes the true temperature through."""

    def read(self, temperature_c: float) -> float:
        return temperature_c

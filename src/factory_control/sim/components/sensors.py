"""Measurement layer: true physical state -> what instruments report (D-22).

NOT IMPLEMENTED. Sensor models (noise, quantization, lag, hysteresis, faults) are
to be designed (docs/plant-model.md section 2.4). PLACEHOLDERS pass values through.
"""

from __future__ import annotations

from factory_control.config import LoadCellConfig


class LevelSwitch:
    """Point level switch. PLACEHOLDER: ideal threshold."""

    def __init__(self, threshold_kg: float) -> None:
        self.threshold_kg = threshold_kg

    def read(self, mass_kg: float) -> bool:
        return mass_kg >= self.threshold_kg


class LoadCell:
    """Hopper weighing (D-21). PLACEHOLDER: passes the true mass through."""

    def __init__(self, cfg: LoadCellConfig) -> None:
        self.cfg = cfg

    def read(self, mass_kg: float) -> float:
        return mass_kg


class Thermocouple:
    """Temperature sensor. PLACEHOLDER: passes the true temperature through."""

    def read(self, temperature_c: float) -> float:
        return temperature_c

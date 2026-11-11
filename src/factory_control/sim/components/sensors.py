"""Measurement layer: true physical state -> what instruments report (D-22).

Every sensor is meant to be a deliberate model (noise, quantization, lag,
hysteresis), switchable one at a time so its effect on the analyzer can be
studied. PLACEHOLDERS below are ideal except for quantization.
"""

from __future__ import annotations

from factory_control.config import LoadCellConfig


class LevelSwitch:
    """Point level switch. PLACEHOLDER: ideal threshold; no hysteresis, debounce, jitter."""

    def __init__(self, threshold_kg: float) -> None:
        self.threshold_kg = threshold_kg

    def read(self, mass_kg: float) -> bool:
        return mass_kg >= self.threshold_kg


class LoadCell:
    """Hopper weighing. PLACEHOLDER: ideal, quantized. To model (D-21): noise,
    vibration coupling from the machine underneath, zero drift."""

    def __init__(self, cfg: LoadCellConfig) -> None:
        self.cfg = cfg

    def read(self, mass_kg: float) -> float:
        return round(mass_kg / self.cfg.resolution_kg) * self.cfg.resolution_kg


class Thermocouple:
    """Temperature sensor. PLACEHOLDER: ideal. To model: lag, noise, open-circuit fault."""

    def read(self, temperature_c: float) -> float:
        return temperature_c

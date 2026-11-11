"""Measurement layer: true physical state -> what the instruments report.

Each sensor is a deliberate model, not an identity function, because the
analyzer must be robust to realistic measurement imperfection (D-14):

    speed        encoder/VFD estimate: quantization, small noise, update rate
    current      VFD output current estimate: noise, filtering inside the drive
    temperature  RTD/PTC on the winding: sensor lag, noise
    load cell    weighed hopper: resolution, noise, screw vibration coupling into
                 the scale, drift; invalid while a batch is pouring in (D-26)
    level switch capacitive/vibrating-fork: threshold + hysteresis + debounce,
                 and pellets heap at an angle of repose, so "mass" is not "level"
    vibration    accelerometer: noise floor, finite bandwidth, gain error

Sensor faults (stuck-at, drift, dropout, chatter) are applied here only.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import HopperConfig, LoadCellConfig


@dataclass(frozen=True, slots=True)
class Measurements:
    speed_setpoint_rpm: float
    speed_rpm: float
    temperature_c: float
    current_a: float
    level_low: bool
    level_high: bool
    hopper_weight_kg: float | None  # None when no load cell is fitted


class LevelSwitch:
    """Point level switch. PLACEHOLDER: ideal threshold, no hysteresis or debounce."""

    def __init__(self, threshold_kg: float) -> None:
        self.threshold_kg = threshold_kg

    def read(self, mass_kg: float) -> bool:
        return mass_kg >= self.threshold_kg


class LoadCell:
    """Hopper weighing. PLACEHOLDER: ideal, quantized to the configured resolution."""

    def __init__(self, cfg: LoadCellConfig) -> None:
        self.cfg = cfg

    def read(self, mass_kg: float) -> float:
        return round(mass_kg / self.cfg.resolution_kg) * self.cfg.resolution_kg


class SensorSuite:
    def __init__(self, hopper_cfg: HopperConfig) -> None:
        self.low = LevelSwitch(hopper_cfg.low_switch_kg)
        self.high = LevelSwitch(hopper_cfg.high_switch_kg)
        self.load_cell = LoadCell(hopper_cfg.load_cell) if hopper_cfg.load_cell else None

    def measure(
        self,
        *,
        setpoint_rpm: float,
        speed_rpm: float,
        temperature_c: float,
        current_a: float,
        hopper_mass_kg: float,
    ) -> Measurements:
        # PLACEHOLDER: ideal sensors.
        return Measurements(
            speed_setpoint_rpm=setpoint_rpm,
            speed_rpm=speed_rpm,
            temperature_c=temperature_c,
            current_a=current_a,
            level_low=self.low.read(hopper_mass_kg),
            level_high=self.high.read(hopper_mass_kg),
            hopper_weight_kg=self.load_cell.read(hopper_mass_kg) if self.load_cell else None,
        )

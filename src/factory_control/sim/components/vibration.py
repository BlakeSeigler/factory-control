"""Synthetic accelerometer signal (shredder and extruder).

NOT IMPLEMENTED. Candidate (docs/plant-model.md section 2.3, D-24): sum of
speed-proportional tones (1x, 2x, gear mesh, bearing defect orders) plus noise,
plus for the shredder an impulsive cutting-load component. Blocks are generated
analytically per publish with phase continuity, so physics can step at 100 Hz
while the signal is sampled at kHz rates.
"""

from __future__ import annotations

import numpy as np

from factory_control.config import VibrationConfig


class VibrationSynth:
    def __init__(self, cfg: VibrationConfig, rng: np.random.Generator) -> None:
        self.cfg = cfg
        self.rng = rng

    @property
    def block_duration_s(self) -> float:
        return self.cfg.block_size / self.cfg.sample_rate_hz

    def next_block(self, motor_speed_rpm: float) -> np.ndarray:
        del motor_speed_rpm  # PLACEHOLDER: silent sensor
        return np.zeros(self.cfg.block_size)

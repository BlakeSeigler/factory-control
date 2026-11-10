"""Synthetic accelerometer signal generator.

NOT IMPLEMENTED. Candidate (docs/plant-model.md section 6): sum of sinusoids at
kinematic frequencies that scale with shaft speed, plus broadband noise:

    a(t) = sum_k A_k(omega, faults) * sin(2*pi*f_k(omega)*t + phi_k) + noise

    f_k in {1x motor, 2x motor (misalignment), gear mesh = z * f_shaft,
            screw 1x, bearing BPFO/BPFI/BSF/FTF, VFD carrier sidebands, ...}

Blocks are generated analytically per publish (not per physics step) with phase
continuity across blocks, so physics can run at 100 Hz while the signal is
sampled at e.g. 2560 Hz.
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
        # PLACEHOLDER: silent sensor.
        del motor_speed_rpm
        return np.zeros(self.cfg.block_size)

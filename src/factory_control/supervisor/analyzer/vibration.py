"""Rule 3: anomalous vibration from the spectrum of the accelerometer signal.

Candidate pipeline (docs/analyzer.md section 3, D-36):

  1. per block: detrend, Hann window, rFFT (or Welch over several blocks)
  2. order-normalize: express frequency as multiples of the current shaft speed,
     because every kinematic tone moves with RPM
  3. features: energy in bands around 1x, 2x, gear mesh, bearing defect orders,
     plus overall RMS (velocity RMS for ISO 20816-style severity)
  4. baseline: per-feature mean/std learned from N healthy blocks, ideally
     bucketed by speed range
  5. score: max z-score (or Mahalanobis distance) vs. threshold_sigma, with an
     on-delay of k consecutive blocks before RAISE

Open: who decides what is "healthy" for the baseline; how to handle speed
transients (skip blocks where speed changed > x% within the block).
"""

from __future__ import annotations

import numpy as np

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import VibrationAnalyzerConfig
from factory_control.supervisor.analyzer.base import Rule


def amplitude_spectrum(block: np.ndarray, fs_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Single-sided amplitude spectrum with a Hann window (amplitude-corrected).

    Returns (frequencies_hz, amplitude). Kept here as a utility for the rule and
    for notebooks; the feature extraction built on it is not decided yet.
    """
    n = block.size
    window = np.hanning(n)
    spec = np.fft.rfft((block - block.mean()) * window)
    amp = 2.0 * np.abs(spec) / window.sum()
    return np.fft.rfftfreq(n, d=1.0 / fs_hz), amp


class VibrationAnomalyRule(Rule):
    name = "vibration_anomaly"
    inputs = frozenset({T.VIB_WAVEFORM.key, T.VIB_SAMPLE_RATE.key, T.SPEED.key})
    requires = frozenset({T.VIB_WAVEFORM.key})

    def __init__(self, device_id: str, cfg: VibrationAnalyzerConfig) -> None:
        super().__init__(device_id)
        self.cfg = cfg

    def on_sample(self, sample: Sample) -> list[AlarmEvent]:
        # NOT IMPLEMENTED
        del sample
        return []

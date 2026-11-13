"""Rule 3 (vibration_anomaly): anomalous vibration in the accelerometer spectrum.

NOT IMPLEMENTED. Design options: docs/analyzer.md section 3 (D-24, D-36).
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.supervisor.analyzer.base import Rule


class VibrationAnomalyRule(Rule):
    name = "vibration_anomaly"
    inputs = frozenset({T.VIB_WAVEFORM.key, T.VIB_SAMPLE_RATE.key, T.SPEED.key})
    requires = frozenset({T.VIB_WAVEFORM.key})

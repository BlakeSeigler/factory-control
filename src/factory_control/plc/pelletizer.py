"""Pelletizer PLC: publishes the strand count from the strand-break detector.

TODO(D-47): what the PLC does on a strand break (alarm only, or slow/stop).
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.plc.base import DevicePLC


class PelletizerPLC(DevicePLC):
    def local_logic(self, dt: float) -> None:
        del dt
        present = self.plant.measure()[T.STRANDS_PRESENT.key]
        self.plc_values[T.STRANDS_COUNT.key] = float(sum(present))

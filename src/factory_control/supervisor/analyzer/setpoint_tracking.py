"""Rule 1: a setpoint was changed but the speed is not following it.

Candidate logic (docs/analyzer.md section 1, decisions D-33, D-34):

  on SpeedSetpoint change with |delta| >= min_step_rpm:
      arm a timer at t0 = sample time, remember sp and pv(t0)
  on Speed sample while armed:
      if |sp - pv| <= deadband_rpm: disarm, clear any active alarm
  on tick while armed:
      if now - t0 > timeout_s and still outside deadband: RAISE

Open: fixed timeout vs. a model-predicted expected trajectory (residual test);
"not moving at all" vs. "moving too slowly" may deserve different messages.
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import SetpointTrackingConfig
from factory_control.supervisor.analyzer.base import Rule


class SetpointTrackingRule(Rule):
    name = "setpoint_tracking"
    inputs = frozenset({T.SPEED_SETPOINT.key, T.SPEED.key})
    requires = inputs

    def __init__(self, device_id: str, cfg: SetpointTrackingConfig) -> None:
        super().__init__(device_id)
        self.cfg = cfg

    def on_sample(self, sample: Sample) -> list[AlarmEvent]:
        # NOT IMPLEMENTED
        del sample
        return []

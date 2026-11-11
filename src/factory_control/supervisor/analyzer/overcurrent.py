"""Rule 4: motor current too high, or rising abnormally fast.

Candidate logic (docs/analyzer.md section 4, D-25). Two independent conditions:

  absolute:  I >= limit_a for on_delay_s                       -> RAISE alarm
  relative:  I >= rise_ratio * baseline for on_delay_s          -> RAISE warning
             baseline = median current over the last baseline_window_s of
             STEADY operation (no setpoint change within that window)

Why gate on setpoint changes: accelerating the screw needs extra torque, so a
healthy speed step produces a current surge. Without the gate, every setpoint
change would look like a jam.

Disabled until the limits in config are chosen; with all of them null the rule
never raises.
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import OvercurrentConfig
from factory_control.supervisor.analyzer.base import Rule


class OvercurrentRule(Rule):
    name = "overcurrent"
    inputs = frozenset({T.MOTOR_CURRENT.key, T.SPEED_SETPOINT.key, T.SPEED.key})

    def __init__(self, machine_id: str, cfg: OvercurrentConfig) -> None:
        super().__init__(machine_id)
        self.cfg = cfg

    @property
    def enabled(self) -> bool:
        return self.cfg.configured

    def on_sample(self, sample: Sample) -> list[AlarmEvent]:
        if not self.enabled:
            return []
        # NOT IMPLEMENTED
        del sample
        return []

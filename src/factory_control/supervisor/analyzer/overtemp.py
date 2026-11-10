"""Rule 2: motor temperature too high.

Candidate logic (docs/analyzer.md section 2, D-23): two thresholds with
hysteresis to avoid alarm chatter around the limit:

    RAISE warning at T >= warn_c,   CLEAR at T < warn_c  - hysteresis_c
    RAISE alarm   at T >= alarm_c,  CLEAR at T < alarm_c - hysteresis_c

Open: add a rate-of-rise (dT/dt) term so a winding short is flagged before the
absolute limit is reached; optional on-delay to reject single-sample spikes.
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.common.messages import AlarmEvent, Sample
from factory_control.config import OvertempConfig
from factory_control.supervisor.analyzer.base import Rule


class OvertempRule(Rule):
    name = "overtemp"
    inputs = frozenset({T.MOTOR_TEMP.key})

    def __init__(self, machine_id: str, cfg: OvertempConfig) -> None:
        super().__init__(machine_id)
        self.cfg = cfg

    def on_sample(self, sample: Sample) -> list[AlarmEvent]:
        # NOT IMPLEMENTED
        del sample
        return []

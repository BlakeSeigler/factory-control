"""Rule 1 (setpoint_tracking): a speed setpoint changed but the speed is not following.

NOT IMPLEMENTED. Design options: docs/analyzer.md section 1 (D-33, D-34).
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.supervisor.analyzer.base import Rule


class SetpointTrackingRule(Rule):
    name = "setpoint_tracking"
    inputs = frozenset({T.SPEED_SETPOINT.key, T.SPEED.key})
    requires = inputs

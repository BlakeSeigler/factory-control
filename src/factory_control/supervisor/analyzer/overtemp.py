"""Rule 2 (overtemp): motor temperature too high.

NOT IMPLEMENTED. Design options: docs/analyzer.md section 2 (D-35).
"""

from __future__ import annotations

from factory_control.common import tags as T
from factory_control.supervisor.analyzer.base import Rule


class OvertempRule(Rule):
    name = "overtemp"
    inputs = frozenset({T.MOTOR_TEMP.key})
    requires = inputs

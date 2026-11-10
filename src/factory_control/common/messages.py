"""Plain data records passed between supervisor components (client -> bus -> consumers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class Sample:
    """One value change received from a machine."""

    machine_id: str
    tag: str  # Tag.key
    value: Any  # float | bool | str | list[float]
    source_ts: float  # unix seconds, from the OPC UA SourceTimestamp (sim clock)
    status: int = 0  # OPC UA StatusCode value; 0 = Good


class Severity(StrEnum):
    WARNING = "warning"
    ALARM = "alarm"


class AlarmTransition(StrEnum):
    RAISED = "raised"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class AlarmEvent:
    """Emitted by an analyzer rule when a condition becomes active or returns to normal."""

    ts: float
    machine_id: str
    rule: str
    severity: Severity
    transition: AlarmTransition
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SetpointCommand:
    ts: float
    machine_id: str
    rpm: float
    source: str  # "operator" | "mpc" | ...

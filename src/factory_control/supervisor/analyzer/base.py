"""Rule interface.

A rule instance is bound to ONE device and owns that device's detection state.
Which devices get which rules follows from the tags they expose (``requires``).
Rules are driven by sample time (OPC UA SourceTimestamp), never wall-clock time,
so they behave identically in real time, accelerated sim, and offline replay of
the historian (D-32). ``on_tick`` exists for timeout-style conditions that must
fire even when no new sample arrives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from factory_control.common.messages import AlarmEvent, Sample


class Rule(ABC):
    name: ClassVar[str]
    inputs: ClassVar[frozenset[str]]  # tag keys this rule consumes
    # A rule is instantiated only for devices exposing all of these tags, e.g. the
    # overtemp rule exists for the shredder and extruder but not the water bath.
    requires: ClassVar[frozenset[str]]

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id

    @abstractmethod
    def on_sample(self, sample: Sample) -> list[AlarmEvent]: ...

    def on_tick(self, now: float) -> list[AlarmEvent]:
        del now
        return []

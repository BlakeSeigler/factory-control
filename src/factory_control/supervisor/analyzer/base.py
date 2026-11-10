"""Rule interface.

A rule instance is bound to ONE machine and owns that machine's detection state.
Rules are driven by sample time (OPC UA SourceTimestamp), never wall-clock time,
so they behave identically in real time, accelerated sim, and offline replay of
the historian (D-19). ``on_tick`` exists for timeout-style conditions that must
fire even when no new sample arrives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from factory_control.common.messages import AlarmEvent, Sample


class Rule(ABC):
    name: ClassVar[str]
    inputs: ClassVar[frozenset[str]]  # tag keys this rule consumes

    def __init__(self, machine_id: str) -> None:
        self.machine_id = machine_id

    @abstractmethod
    def on_sample(self, sample: Sample) -> list[AlarmEvent]: ...

    def on_tick(self, now: float) -> list[AlarmEvent]:
        del now
        return []

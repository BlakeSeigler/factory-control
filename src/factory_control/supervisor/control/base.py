"""Controller interface.

A controller runs at a fixed period, reads the latest line state, and returns
setpoint commands. It never talks OPC UA itself; the supervisor writes the
commands, which keeps controllers testable against the plant model offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from factory_control.common.messages import SetpointCommand
from factory_control.supervisor.state import StateCache


@dataclass(frozen=True, slots=True)
class LineTarget:
    """What the operator asks of the line: pellet output. How it is set is D-45."""

    output_kg_h: float


class Controller(ABC):
    @abstractmethod
    def step(
        self, now: float, state: StateCache, target: LineTarget | None
    ) -> list[SetpointCommand]: ...


class ManualController(Controller):
    """No automatic action; setpoints come from the operator (``fc write``)."""

    def step(
        self, now: float, state: StateCache, target: LineTarget | None
    ) -> list[SetpointCommand]:
        del now, state, target
        return []

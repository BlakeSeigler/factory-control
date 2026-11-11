"""Model predictive controller for the line (supervisory layer).

NOT IMPLEMENTED. Scope and formulation are open (docs/control.md sections 6-7,
D-41). Leading candidate: one MPC over the shredder + extruder section

  manipulated   shredder speed, extruder speed (optionally barrel setpoint)
  controlled    line output (tracking), extruder hopper mass (keep in band)
  constraints   speed and ramp limits; motor temperature and current limits;
                heater output not saturated; hopper levels (soft)

with the pelletizer kept OUTSIDE the MPC as a ratio follower of the estimated
throughput (it is algebraic and fast: nothing for an optimizer to plan).
"""

from __future__ import annotations

from factory_control.common.messages import SetpointCommand
from factory_control.supervisor.control.base import Controller, LineTarget
from factory_control.supervisor.state import StateCache


class MpcController(Controller):
    def step(
        self, now: float, state: StateCache, target: LineTarget | None
    ) -> list[SetpointCommand]:
        raise NotImplementedError("see docs/control.md")

"""Baseline supervisory controller: feed-forward + ratio + trim. No optimizer.

NOT IMPLEMENTED. Structure (docs/control.md section 4), with target output m*:

  extruder     n_ext = m* / K_ext                                   feed-forward
  pelletizer   n_pel = m_hat / (strands * knives * b * m_pellet*)  ratio to throughput
               m_hat = K_ext_hat * n_ext  (fast), K_ext_hat re-calibrated slowly from
               the shredder hopper's load cell
  shredder     n_shr = m* / K_shr + PI(extruder hopper level estimate)   buffer trim
  barrel       setpoint left to the operator / recipe; the PLC's PID holds it

This is the benchmark the MPC has to beat (D-40).
"""

from __future__ import annotations

from factory_control.common.messages import SetpointCommand
from factory_control.supervisor.control.base import Controller, LineTarget
from factory_control.supervisor.state import StateCache


class BaselineController(Controller):
    def step(
        self, now: float, state: StateCache, target: LineTarget | None
    ) -> list[SetpointCommand]:
        raise NotImplementedError("see docs/control.md section 4")

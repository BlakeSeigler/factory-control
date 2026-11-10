"""Model predictive controller for the line.

NOT IMPLEMENTED. Candidate formulation (docs/mpc.md section 5):

  minimize over u[0..N-1]
      sum_k  q_f * (m_dot_line[k] - m_dot_target)^2
           + q_m * (M_2[k] - M_2_ref)^2
           + r   * ||u[k] - u[k-1]||^2
  subject to
      model dynamics (control/model.py)
      rpm_min <= u[k] <= rpm_max
      |u[k] - u[k-1]| <= du_max
      M_low <= M_2[k] <= M_high          (soft, slack-penalized)

Solve as a QP each control period (receding horizon); apply u[0] only. Solver
choice (OSQP via cvxpy, CasADi, hand-rolled condensed QP) is D-34.
"""

from __future__ import annotations

from factory_control.common.messages import SetpointCommand
from factory_control.supervisor.control.base import Controller, LineTarget
from factory_control.supervisor.state import StateCache


class MpcController(Controller):
    def step(
        self, now: float, state: StateCache, target: LineTarget | None
    ) -> list[SetpointCommand]:
        raise NotImplementedError("see docs/mpc.md")

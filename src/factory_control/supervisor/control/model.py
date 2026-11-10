"""Prediction model used inside the MPC.

NOT IMPLEMENTED. Candidate (docs/mpc.md section 3), discrete time, step Ts:

  states   x = [omega_1, omega_2, M_1, M_2]        motor speeds, hopper masses
  inputs   u = [omega_sp_1, omega_sp_2]            RPM setpoints
  outputs  y = [m_dot_line, M_2]                   line flow, buffer hopper mass

  omega_i[k+1] = a_i * omega_i[k] + (1 - a_i) * u_i[k],     a_i = exp(-Ts / tau_i)
  m_dot_i      = K_i * omega_i                               K_i = rho * V / (60 * gear_i)
  M_1[k+1]     = M_1[k] + Ts * (m_dot_supply - K_1 * omega_1[k])
  M_2[k+1]     = M_2[k] + Ts * (K_1 * omega_1[k] - K_2 * omega_2[k])
  m_dot_line   = K_2 * omega_2

This is linear, so the MPC is a convex QP. Starve-feeding (K_i depending on M_i)
makes it nonlinear; whether we keep the linear model plus a disturbance
estimate or go nonlinear is D-32.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class LinearModel:
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    Ts: float


def build_line_model(*args: object, **kwargs: object) -> LinearModel:
    raise NotImplementedError("see docs/mpc.md section 3")

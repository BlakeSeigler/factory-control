"""Drive + motor speed dynamics.

CURRENT MODEL (placeholder, sufficient for the dashboard vertical slice):
first-order lag towards the setpoint, with the VFD's acceleration ramp as a
rate limit:

    d(omega)/dt = clamp((omega_sp - omega) / tau, -a_max, +a_max)

This ignores load torque entirely, so a jam cannot slow the motor yet. The
candidate replacement (torque balance with a VFD slip/current-limit model) is in
docs/plant-model.md section 2 and decision D-10.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import MotorConfig


@dataclass(slots=True)
class MotorState:
    speed_rpm: float
    setpoint_rpm: float


class Motor:
    def __init__(self, cfg: MotorConfig) -> None:
        self.cfg = cfg
        self.state = MotorState(speed_rpm=cfg.initial_rpm, setpoint_rpm=cfg.initial_rpm)

    def command(self, setpoint_rpm: float) -> float:
        """Accept a speed command; returns the value actually applied after clamping."""
        applied = min(max(setpoint_rpm, self.cfg.min_rpm), self.cfg.max_rpm)
        self.state.setpoint_rpm = applied
        return applied

    def step(self, dt: float, load_torque_nm: float = 0.0) -> None:
        # TODO(D-10): load_torque_nm is accepted but unused until the torque model lands.
        del load_torque_nm
        s, c = self.state, self.cfg
        rate = (s.setpoint_rpm - s.speed_rpm) / c.time_constant_s
        rate = min(max(rate, -c.max_accel_rpm_s), c.max_accel_rpm_s)
        s.speed_rpm += rate * dt

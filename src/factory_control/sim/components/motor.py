"""Drive + motor speed dynamics (used by shredder, extruder, pelletizer).

CURRENT MODEL (placeholder, enough for the dashboard vertical slice):
first-order lag towards the setpoint with the VFD's acceleration ramp as a rate
limit:

    d(omega)/dt = clamp((omega_sp - omega) / tau, -a_max, +a_max)

Load has no effect, so jams cannot slow the motor and current stays 0. The
recommended replacement (VFD speed loop + torque limit + mechanics, from which
current follows) is docs/plant-model.md section 2.1, decision D-15.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import MotorConfig


@dataclass(slots=True)
class MotorState:
    speed_rpm: float
    setpoint_rpm: float
    current_a: float = 0.0  # PLACEHOLDER until the torque model exists (D-15)


class Motor:
    def __init__(self, cfg: MotorConfig) -> None:
        self.cfg = cfg
        self.state = MotorState(speed_rpm=cfg.initial_rpm, setpoint_rpm=cfg.initial_rpm)

    def command(self, setpoint_rpm: float) -> float:
        """Speed command to the drive; returns the value actually applied after clamping."""
        applied = min(max(setpoint_rpm, self.cfg.min_rpm), self.cfg.max_rpm)
        self.state.setpoint_rpm = applied
        return applied

    def step(self, dt: float, load_torque_nm: float = 0.0) -> None:
        del load_torque_nm  # TODO(D-15): used once the torque model lands
        s, c = self.state, self.cfg
        rate = (s.setpoint_rpm - s.speed_rpm) / c.time_constant_s
        rate = min(max(rate, -c.max_accel_rpm_s), c.max_accel_rpm_s)
        s.speed_rpm += rate * dt

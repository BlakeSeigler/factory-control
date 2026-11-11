"""Discrete PID controller, the equivalent of a PLC's standard PID function block.

On real equipment you do not write this: every PLC ships one (e.g. Siemens
PID_Compact, Rockwell PIDE, CODESYS PID) and the work is configuring and tuning
it. In simulation there is no PLC, so this module plays that role. It implements
what those blocks do and nothing more:

    u = Kp*e + Ki*integral(e) - Kd*d(pv)/dt

  * derivative on the measurement, not the error, so a setpoint step does not
    produce a derivative kick;
  * anti-windup by conditional integration: the integral stops growing while the
    output is saturated in the direction the error pushes it;
  * output clamped to [out_min, out_max].
"""

from __future__ import annotations

from factory_control.config import PidConfig


class Pid:
    def __init__(self, cfg: PidConfig, setpoint: float = 0.0) -> None:
        self.cfg = cfg
        self.setpoint = setpoint
        self.integral = 0.0
        self._last_pv: float | None = None
        self.output = cfg.out_min

    def reset(self) -> None:
        self.integral = 0.0
        self._last_pv = None

    def update(self, pv: float, dt: float) -> float:
        c = self.cfg
        error = self.setpoint - pv
        d_pv = 0.0 if self._last_pv is None else (pv - self._last_pv) / dt
        self._last_pv = pv

        unclamped = c.kp * error + c.ki * self.integral - c.kd * d_pv
        saturated_high = unclamped >= c.out_max and error > 0
        saturated_low = unclamped <= c.out_min and error < 0
        if not (saturated_high or saturated_low):
            self.integral += error * dt

        u = c.kp * error + c.ki * self.integral - c.kd * d_pv
        self.output = min(max(u, c.out_min), c.out_max)
        return self.output

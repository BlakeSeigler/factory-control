"""PID controller: the simulation's stand-in for a PLC's standard PID function block.

NOT IMPLEMENTED. Structure, anti-windup, derivative handling, time-proportioning
and tuning are open (docs/control.md section 2, D-26).
"""

from __future__ import annotations


class Pid:
    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        raise NotImplementedError("D-26")

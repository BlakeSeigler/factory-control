"""PID controller: the simulation's stand-in for a PLC's standard PID function block.

NOT IMPLEMENTED. Design questions (structure, anti-windup, derivative handling,
time-proportioning, tuning): docs/control.md section 2, D-26.
"""

from __future__ import annotations

from factory_control.config import PidConfig


class Pid:
    def __init__(self, cfg: PidConfig, setpoint: float = 0.0) -> None:
        self.cfg = cfg
        self.setpoint = setpoint

    def update(self, pv: float, dt: float) -> float:
        raise NotImplementedError("D-26")

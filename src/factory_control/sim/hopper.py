"""Hopper mass balance.

    dM/dt = m_dot_in - m_dot_out,   0 <= M <= capacity

Overflow above capacity is spilled and must be reported (it is a real failure
mode in a series line). Level geometry (mass -> height at the switches) is open:
D-13.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import HopperConfig


@dataclass(slots=True)
class HopperState:
    mass_kg: float
    spilled_kg: float = 0.0


class Hopper:
    def __init__(self, cfg: HopperConfig) -> None:
        self.cfg = cfg
        self.state = HopperState(mass_kg=cfg.initial_kg)

    def step(self, dt: float, inflow_kg_s: float, outflow_kg_s: float) -> float:
        """Integrate the mass balance; returns the outflow actually delivered (kg/s).

        PLACEHOLDER: holds mass constant. Implementation must clip outflow when the
        hopper is empty and account spill when full.
        """
        del dt, inflow_kg_s
        return outflow_kg_s

"""Hopper mass balance (shredder and extruder hoppers).

    dM/dt = m_dot_in - m_dot_out,   0 <= M <= capacity   (overflow is spilled)

NOT IMPLEMENTED beyond the interface: mass is held constant. The implementation
must clip outflow when empty and account spill when full (docs/plant-model.md 3.1).
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

    def step(self, dt: float, inflow_kg_s: float, demand_kg_s: float) -> float:
        """Integrate; returns the outflow actually delivered (kg/s). PLACEHOLDER: holds mass."""
        del dt, inflow_kg_s
        return demand_kg_s

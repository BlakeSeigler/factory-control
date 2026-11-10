"""Screw conveyance: screw speed -> discharged mass flow.

NOT IMPLEMENTED. Candidate model (docs/plant-model.md section 3):

    m_dot = rho_bulk * V_disp * (n_screw / 60) * eta_fill(level, faults)

where eta_fill in [0, 1] captures starve feeding at low hopper level, bridging,
and wear. Also produces the load torque fed back to the motor (D-10, D-11).
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_control.config import ScrewConfig


@dataclass(slots=True)
class ScrewOutput:
    mass_flow_kg_s: float
    load_torque_nm: float


class Screw:
    def __init__(self, cfg: ScrewConfig) -> None:
        self.cfg = cfg

    def step(self, screw_rpm: float, hopper_mass_kg: float) -> ScrewOutput:
        # PLACEHOLDER: no material moves until the conveyance model is agreed.
        del screw_rpm, hopper_mass_kg
        return ScrewOutput(mass_flow_kg_s=0.0, load_torque_nm=0.0)

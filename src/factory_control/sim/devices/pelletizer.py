"""Strand pelletizer: feed rolls pull the strands, a rotor with ``knives`` cuts them.

One motor drives both through fixed ratios (D-10), so with motor speed n [rpm]:

    strand speed       v   = a * n               [m/min]  a = strand_speed_m_min_per_rpm
    rotor speed        n_r = b * n               [rpm]    b = rotor_rpm_per_motor_rpm
    cuts per minute    per strand = knives * n_r
    pellet length      L = v / (knives * n_r) = a / (knives * b)         constant (geometry)
    pellet mass        m_p = m_dot / (strands * knives * n_r)            depends on flow!

So with fixed gearing, pellet LENGTH is fixed and pellet MASS (size) follows the
strand diameter, which is set by how fast the strands are pulled relative to how
fast the extruder pushes them out (draw-down). Equal pellets require n
proportional to m_dot: that is the "match cutting to mass flow" requirement
(docs/control.md section 5). The functions below are exact consequences of the
geometry and are implemented; the strand dynamics (sag, breaks) are not (D-19).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from factory_control.common import tags as T
from factory_control.config import MaterialConfig, PelletizerDeviceConfig
from factory_control.sim.components.motor import Motor
from factory_control.sim.devices.base import DevicePlant


class PelletizerPlant(DevicePlant):
    cfg: PelletizerDeviceConfig

    def __init__(
        self, cfg: PelletizerDeviceConfig, material: MaterialConfig, rng: np.random.Generator
    ) -> None:
        super().__init__(cfg, material, rng)
        self.motor = Motor(cfg.motor)
        self.inflow_kg_s = 0.0

    # geometry (exact) ----------------------------------------------------------------

    def pellet_length_m(self) -> float:
        c = self.cfg.cutter
        return c.strand_speed_m_min_per_rpm / (c.knives * c.rotor_rpm_per_motor_rpm)

    def pellet_mass_kg(self, mass_flow_kg_s: float, motor_rpm: float) -> float:
        c = self.cfg.cutter
        cuts_per_s = c.strands * c.knives * c.rotor_rpm_per_motor_rpm * motor_rpm / 60.0
        return mass_flow_kg_s / cuts_per_s if cuts_per_s > 0 else math.inf

    def strand_diameter_m(self, mass_flow_kg_s: float, motor_rpm: float) -> float:
        c = self.cfg.cutter
        v_m_s = c.strand_speed_m_min_per_rpm * motor_rpm / 60.0
        if v_m_s <= 0:
            return math.inf
        area = mass_flow_kg_s / (c.strands * self.material.solid_density_kg_m3 * v_m_s)
        return math.sqrt(4.0 * area / math.pi)

    # physics -------------------------------------------------------------------------

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        del t
        self.inflow_kg_s = inflow_kg_s  # PLACEHOLDER: no strand dynamics (D-19)
        self.motor.step(dt)
        return inflow_kg_s

    def measure(self) -> dict[str, Any]:
        return {T.SPEED.key: self.motor.state.speed_rpm}

    def truth(self) -> dict[str, float]:
        n = self.motor.state.speed_rpm
        return {
            "pellet_mass_g": 1000.0 * self.pellet_mass_kg(self.inflow_kg_s, n),
            "pellet_length_mm": 1000.0 * self.pellet_length_m(),
        }

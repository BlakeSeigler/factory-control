import math

import numpy as np

from factory_control.config import load_config
from factory_control.sim.devices.pelletizer import PelletizerPlant


def plant():
    cfg = load_config("config/line.yaml")
    return PelletizerPlant(cfg.device("pelletizer"), cfg.sim.material, np.random.default_rng(0))


def test_pellet_length_is_fixed_by_gearing():
    assert math.isclose(plant().pellet_length_m(), 0.075 / 24)


def test_equal_pellets_need_speed_proportional_to_flow():
    p = plant()
    m1 = p.pellet_mass_kg(mass_flow_kg_s=0.05, motor_rpm=1000)
    m2 = p.pellet_mass_kg(mass_flow_kg_s=0.10, motor_rpm=2000)
    m_wrong = p.pellet_mass_kg(mass_flow_kg_s=0.10, motor_rpm=1000)
    assert math.isclose(m1, m2)
    assert math.isclose(m_wrong, 2 * m1)


def test_pellet_mass_consistent_with_strand_geometry():
    p = plant()
    flow, rpm = 0.07, 1000.0
    d = p.strand_diameter_m(flow, rpm)
    volume = math.pi * d**2 / 4 * p.pellet_length_m()
    assert math.isclose(volume * 950.0, p.pellet_mass_kg(flow, rpm), rel_tol=1e-9)

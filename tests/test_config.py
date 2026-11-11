import pytest
from pydantic import ValidationError

from factory_control.config import HopperConfig, load_config


def test_repo_config_loads():
    cfg = load_config("config/line.yaml")
    assert [m.id for m in cfg.machines] == cfg.line.machine_order
    endpoints = [m.opcua.endpoint for m in cfg.machines]
    assert len(set(endpoints)) == len(endpoints), "each machine needs its own server"


def test_hopper_switch_order_is_validated():
    with pytest.raises(ValidationError):
        HopperConfig(capacity_kg=10, low_switch_kg=8, high_switch_kg=5, initial_kg=1)

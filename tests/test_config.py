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


def test_overcurrent_rule_disabled_until_limits_chosen():
    from factory_control.common.messages import Sample
    from factory_control.config import OvercurrentConfig
    from factory_control.supervisor.analyzer.overcurrent import OvercurrentRule

    cfg = load_config("config/line.yaml")
    assert not cfg.supervisor.analyzer.overcurrent.configured
    rule = OvercurrentRule("feeder_1", cfg.supervisor.analyzer.overcurrent)
    assert rule.on_sample(Sample("feeder_1", "motor.current_a", 1e6, 0.0)) == []
    assert OvercurrentConfig(limit_a=20.0).configured
    assert not OvercurrentConfig(rise_ratio=1.5).configured  # needs a baseline window too

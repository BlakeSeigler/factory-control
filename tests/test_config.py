import pytest
from pydantic import ValidationError

from factory_control.config import HopperConfig, load_config


def test_repo_config_loads_in_line_order():
    cfg = load_config("config/line.yaml")
    assert [cfg.device(d).type for d in cfg.line.material_path] == [
        "shredder", "extruder", "water_bath", "pelletizer",
    ]  # fmt: skip


def test_only_first_hopper_is_weighed():
    cfg = load_config("config/line.yaml")
    assert cfg.device("shredder").instruments == {"hopper_load_cell"}
    assert cfg.device("extruder").instruments == frozenset()


def test_hopper_switch_order_is_validated():
    with pytest.raises(ValidationError):
        HopperConfig(capacity_kg=10, low_switch_kg=8, high_switch_kg=5, initial_kg=1)


def test_reordered_material_path_is_rejected():
    import yaml

    from factory_control.config import AppConfig

    with open("config/line.yaml") as f:
        raw = yaml.safe_load(f)
    raw["line"]["material_path"] = ["extruder", "shredder", "water_bath", "pelletizer"]
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)

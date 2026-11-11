from factory_control.common import tags as T
from factory_control.config import load_config
from factory_control.supervisor.analyzer.engine import build_rules


def test_rules_follow_device_tags():
    cfg = load_config("config/line.yaml")
    names = {
        d.id: sorted(
            r.name
            for r in build_rules(
                d.id,
                frozenset(t.key for t in T.tags_for(d.type, d.instruments)),
                cfg.supervisor.analyzer,
            )
        )
        for d in cfg.devices
    }
    assert names == {
        "shredder": ["overtemp", "setpoint_tracking", "vibration_anomaly"],
        "extruder": ["overtemp", "setpoint_tracking", "vibration_anomaly"],
        "water_bath": [],
        "pelletizer": ["setpoint_tracking"],
    }

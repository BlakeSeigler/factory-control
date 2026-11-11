from factory_control.common import tags as T


def test_keys_and_paths_unique_per_device_type():
    for dt in T.DEVICE_TYPES.values():
        assert len({t.key for t in dt.tags}) == len(dt.tags), dt.name
        assert len({t.path for t in dt.tags}) == len(dt.tags), dt.name


def test_same_key_means_same_tag_everywhere():
    seen: dict[str, T.Tag] = {}
    for dt in T.DEVICE_TYPES.values():
        for t in dt.tags:
            assert seen.setdefault(t.key, t) == t


def test_writable_tags_are_the_setpoints():
    writable = {dt.name: {t.key for t in dt.tags if t.writable} for dt in T.DEVICE_TYPES.values()}
    assert writable == {
        "shredder": {T.SPEED_SETPOINT.key},
        "extruder": {T.SPEED_SETPOINT.key, T.BARREL_SETPOINT.key},
        "water_bath": set(),
        "pelletizer": {T.SPEED_SETPOINT.key},
    }


def test_load_cell_tag_only_when_fitted():
    assert T.HOPPER_WEIGHT in T.tags_for("shredder", frozenset({"hopper_load_cell"}))
    assert T.HOPPER_WEIGHT not in T.tags_for("shredder")
    assert T.HOPPER_WEIGHT not in T.tags_for("extruder")


def test_arrays_are_not_historized_as_scalars():
    for t in T.ALL_TAGS.values():
        if t.vtype is T.ValueType.DOUBLE_ARRAY:
            assert not t.historize

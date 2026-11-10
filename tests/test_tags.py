from factory_control.common import tags as T


def test_tag_keys_and_paths_unique():
    keys = [t.key for t in T.FEEDER_TAGS]
    paths = [t.path for t in T.FEEDER_TAGS]
    assert len(set(keys)) == len(keys)
    assert len(set(paths)) == len(paths)


def test_only_setpoint_is_writable():
    assert [t.key for t in T.FEEDER_TAGS if t.writable] == [T.SPEED_SETPOINT.key]


def test_arrays_are_not_historized_as_scalars():
    for t in T.FEEDER_TAGS:
        if t.vtype is T.ValueType.DOUBLE_ARRAY:
            assert not t.historize

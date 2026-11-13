"""The tag contract between each device's PLC (OPC UA server) and the supervisor.

Both sides import this module: a PLC builds its address space from it and the
supervisor's client resolves nodes from it. There is no second list to keep in sync.

Tags are grouped into reusable *components* (hopper, motor, vibration, barrel,
bath); a *device type* is a root object plus a set of components:

    Shredder    Identification, Hopper (+Weight), Motor, MotorHealth, Vibration
    Extruder    Identification, Hopper, Motor, MotorHealth, Vibration, Barrel
    WaterBath   Identification, Bath
    Pelletizer  Identification, Motor, MotorHealth, Strands

Example browse path: ``Objects/Extruder/Barrel/TemperatureSetpoint``.
Every server additionally exposes ``Objects/Simulation`` in a separate namespace
(sim only, D-14).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DEVICE_NS_URI = "urn:factory-control:device"
SIM_NS_URI = "urn:factory-control:simulation"
SIM_OBJECT = "Simulation"


class ValueType(StrEnum):
    DOUBLE = "double"
    BOOLEAN = "boolean"
    STRING = "string"
    DOUBLE_ARRAY = "double[]"
    BOOLEAN_ARRAY = "boolean[]"


@dataclass(frozen=True, slots=True)
class Tag:
    key: str  # stable internal id (unique within a device), used in the DB and analyzer
    path: tuple[str, ...]  # browse path below the device's root object
    vtype: ValueType
    unit: str = ""
    writable: bool = False
    historize: bool = True  # stored in the ``sample`` table (scalars only)
    description: str = ""
    requires: str | None = None  # optional instrument; tag exists only if fitted


def _t(key: str, path: str, vtype: ValueType, unit: str = "", **kw: object) -> Tag:
    return Tag(key, tuple(path.split("/")), vtype, unit, **kw)  # type: ignore[arg-type]


D, B, S = ValueType.DOUBLE, ValueType.BOOLEAN, ValueType.STRING

# --- components ------------------------------------------------------------------------

DEVICE_ID = _t("ident.device_id", "Identification/DeviceId", S, historize=False)

LEVEL_LOW = _t(
    "hopper.level_low",
    "Hopper/LevelLow",
    B,
    description="Low level switch; True = material present at switch",
)
LEVEL_HIGH = _t(
    "hopper.level_high",
    "Hopper/LevelHigh",
    B,
    description="High level switch; True = material present at switch",
)
HOPPER_WEIGHT = _t(
    "hopper.weight_kg",
    "Hopper/Weight",
    D,
    "kg",
    requires="hopper_load_cell",
    description="Net material mass from the hopper's load cell (D-03)",
)
HOPPER = (LEVEL_LOW, LEVEL_HIGH, HOPPER_WEIGHT)

SPEED_SETPOINT = _t("motor.speed_setpoint_rpm", "Motor/SpeedSetpoint", D, "rpm", writable=True)
SPEED = _t("motor.speed_rpm", "Motor/Speed", D, "rpm")
MOTOR = (SPEED_SETPOINT, SPEED)

MOTOR_CURRENT = _t(
    "motor.current_a",
    "Motor/Current",
    D,
    "A",
    description="Drive output current (RMS); logged, no rule (D-38)",
)
MOTOR_TEMP = _t("motor.temperature_c", "Motor/Temperature", D, "degC")
MOTOR_HEALTH = (MOTOR_CURRENT, MOTOR_TEMP)

VIB_SAMPLE_RATE = _t("vibration.sample_rate_hz", "Vibration/SampleRate", D, "Hz", historize=False)
VIB_WAVEFORM = _t(
    "vibration.waveform",
    "Vibration/Waveform",
    ValueType.DOUBLE_ARRAY,
    "m/s^2",
    historize=False,
    description="One acceleration block per update",
)
VIBRATION = (VIB_SAMPLE_RATE, VIB_WAVEFORM)

BARREL_SETPOINT = _t(
    "barrel.temperature_setpoint_c",
    "Barrel/TemperatureSetpoint",
    D,
    "degC",
    writable=True,
    description="Setpoint of the PLC's barrel PID",
)
BARREL_TEMP = _t(
    "barrel.temperature_c", "Barrel/Temperature", D, "degC", description="Barrel thermocouple"
)
HEATER_OUTPUT = _t(
    "barrel.heater_output_pct",
    "Barrel/HeaterOutput",
    D,
    "%",
    description="Barrel PID output (heater duty); a PLC value, not a sensor",
)
BARREL = (BARREL_SETPOINT, BARREL_TEMP, HEATER_OUTPUT)

STRANDS_PRESENT = _t(
    "strands.present",
    "Strands/Present",
    ValueType.BOOLEAN_ARRAY,
    historize=False,
    description="Strand-break detector, one entry per strand; True = strand present",
)
STRANDS_COUNT = _t(
    "strands.count",
    "Strands/Count",
    D,
    description="Strands present; PLC-computed from the detector",
)
STRANDS = (STRANDS_PRESENT, STRANDS_COUNT)

BATH_TEMP = _t("bath.water_temperature_c", "Bath/WaterTemperature", D, "degC")
BATH = (BATH_TEMP,)

# --- device types ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceType:
    name: str  # matches config ``type``
    root: str  # root object below Objects/
    tags: tuple[Tag, ...]


DEVICE_TYPES: dict[str, DeviceType] = {
    dt.name: dt
    for dt in (
        DeviceType("shredder", "Shredder", (DEVICE_ID, *HOPPER, *MOTOR, *MOTOR_HEALTH, *VIBRATION)),
        DeviceType(
            "extruder", "Extruder", (DEVICE_ID, *HOPPER, *MOTOR, *MOTOR_HEALTH, *VIBRATION, *BARREL)
        ),
        DeviceType("water_bath", "WaterBath", (DEVICE_ID, *BATH)),
        DeviceType("pelletizer", "Pelletizer", (DEVICE_ID, *MOTOR, *MOTOR_HEALTH, *STRANDS)),
    )
}

ALL_TAGS: dict[str, Tag] = {t.key: t for dt in DEVICE_TYPES.values() for t in dt.tags}


def tags_for(device_type: str, instruments: frozenset[str] = frozenset()) -> tuple[Tag, ...]:
    """The tags a device of this type, with these optional instruments, exposes."""
    return tuple(
        t for t in DEVICE_TYPES[device_type].tags if t.requires is None or t.requires in instruments
    )

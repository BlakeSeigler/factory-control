"""The tag contract between each device's PLC (OPC UA server) and the supervisor.

Both sides import this module: a PLC builds its address space from it and the
supervisor's client resolves nodes from it. There is no second list to keep in sync.

Tags are grouped into *components*; a *device type* is a root object plus a set of
components:

    Shredder    Identification, Hopper (incl. Weight), Motor, MotorHealth, Vibration
    Extruder    Identification, Hopper, Motor, MotorHealth, Vibration, Barrel, Die
    WaterBath   Identification, Bath
    Pelletizer  Identification, Motor, MotorHealth

Example browse path: ``Objects/Extruder/Barrel/TemperatureSetpoint``.

Every server also exposes a sim-only ``Objects/Simulation`` object in a separate
namespace (fault injection and ground truth, D-14). Its names are defined at the
bottom of this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DEVICE_NS_URI = "urn:factory-control:device"


class ValueType(StrEnum):
    DOUBLE = "double"
    BOOLEAN = "boolean"
    STRING = "string"
    DOUBLE_ARRAY = "double[]"


@dataclass(frozen=True, slots=True)
class Tag:
    key: str  # stable internal id, used in the DB and the analyzer
    path: tuple[str, ...]  # browse path below the device's root object
    vtype: ValueType
    unit: str = ""
    writable: bool = False  # a setpoint; its range is enforced by the PLC (D-13)
    historize: bool = True  # stored in the ``sample`` table (scalars only)
    description: str = ""


def _t(key: str, path: str, vtype: ValueType, unit: str = "", **kw: object) -> Tag:
    return Tag(key, tuple(path.split("/")), vtype, unit, **kw)  # type: ignore[arg-type]


D, B, S = ValueType.DOUBLE, ValueType.BOOLEAN, ValueType.STRING

# --- components ------------------------------------------------------------------------

DEVICE_ID = _t("ident.device_id", "Identification/DeviceId", S, historize=False)

# Level switches: True = material present at the switch.
LEVEL_LOW = _t("hopper.level_low", "Hopper/LevelLow", B)
LEVEL_HIGH = _t("hopper.level_high", "Hopper/LevelHigh", B)
HOPPER_WEIGHT = _t(
    "hopper.weight_kg",
    "Hopper/Weight",
    D,
    "kg",
    description="Net material mass from the hopper's load cell (D-03)",
)
HOPPER = (LEVEL_LOW, LEVEL_HIGH)

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
    "barrel.temperature_c",
    "Barrel/Temperature",
    D,
    "degC",
    description="Barrel wall thermocouple; the barrel PID's measurement",
)
HEATER_OUTPUT = _t(
    "barrel.heater_output_pct",
    "Barrel/HeaterOutput",
    D,
    "%",
    description="Barrel PID output (heater duty); a PLC value, not a sensor",
)
BARREL = (BARREL_SETPOINT, BARREL_TEMP, HEATER_OUTPUT)

MELT_TEMP = _t(
    "die.melt_temperature_c",
    "Die/MeltTemperature",
    D,
    "degC",
    description="Thermocouple in the melt stream at the die (D-08)",
)
DIE = (MELT_TEMP,)

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
        DeviceType("shredder", "Shredder",
                   (DEVICE_ID, *HOPPER, HOPPER_WEIGHT, *MOTOR, *MOTOR_HEALTH, *VIBRATION)),
        DeviceType("extruder", "Extruder",
                   (DEVICE_ID, *HOPPER, *MOTOR, *MOTOR_HEALTH, *VIBRATION, *BARREL, *DIE)),
        DeviceType("water_bath", "WaterBath", (DEVICE_ID, *BATH)),
        DeviceType("pelletizer", "Pelletizer", (DEVICE_ID, *MOTOR, *MOTOR_HEALTH)),
    )
}  # fmt: skip

ALL_TAGS: dict[str, Tag] = {t.key: t for dt in DEVICE_TYPES.values() for t in dt.tags}

# --- simulation-only object (D-14) -----------------------------------------------------

SIM_NS_URI = "urn:factory-control:simulation"
SIM_OBJECT = "Simulation"
SIM_ACTIVE_FAULTS = "ActiveFaults"  # String (JSON): ground truth of injected faults
SIM_INJECT_FAULT = "InjectFault"  # method (name, params_json) -> Boolean
SIM_CLEAR_FAULTS = "ClearFaults"  # method () -> Boolean
GROUND_TRUTH_KEY = "sim.active_faults"  # key under which ground truth travels and is stored

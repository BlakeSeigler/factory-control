"""The tag contract between a machine's OPC UA server and the supervisor's client.

Both sides import this module: the server builds its address space from it and the
client resolves nodes from it. Changing a tag here changes it everywhere, which is
the point; there is no second list to keep in sync.

Address space of every feeder (browse names, all in namespace ``FEEDER_NS_URI``)::

    Objects/
      Feeder/
        Identification/MachineId        String   R
        Motor/SpeedSetpoint             Double   RW   rpm
        Motor/Speed                     Double   R    rpm
        Motor/Temperature               Double   R    degC
        Motor/Current                   Double   R    A (drive output current)
        Hopper/LevelLow                 Boolean  R    True = material present at switch
        Hopper/LevelHigh                Boolean  R    True = material present at switch
        Hopper/Weight                   Double   R    kg net material; only if a load cell is fitted
        Vibration/SampleRate            Double   R    Hz
        Vibration/Waveform              Double[] R    m/s^2, one block per update
      Simulation/                       (separate namespace SIM_NS_URI, sim only, D-12)
        ActiveFaults                    String   R    JSON ground truth
        InjectFault(name, params_json)  Method
        ClearFaults()                   Method
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FEEDER_NS_URI = "urn:factory-control:feeder"
SIM_NS_URI = "urn:factory-control:simulation"

ROOT_OBJECT = "Feeder"
SIM_OBJECT = "Simulation"


class ValueType(StrEnum):
    DOUBLE = "double"
    BOOLEAN = "boolean"
    STRING = "string"
    DOUBLE_ARRAY = "double[]"


@dataclass(frozen=True, slots=True)
class Tag:
    key: str  # stable internal id, used in the DB and the analyzer
    path: tuple[str, ...]  # browse path below Objects/Feeder
    vtype: ValueType
    unit: str = ""
    writable: bool = False
    historize: bool = True  # stored in the ``sample`` table (scalars only)
    description: str = ""
    requires: str | None = None  # optional instrument; tag exists only if it is fitted


MACHINE_ID = Tag(
    "ident.machine_id",
    ("Identification", "MachineId"),
    ValueType.STRING,
    historize=False,
    description="Configured machine id",
)
SPEED_SETPOINT = Tag(
    "motor.speed_setpoint_rpm",
    ("Motor", "SpeedSetpoint"),
    ValueType.DOUBLE,
    unit="rpm",
    writable=True,
    description="Commanded motor speed",
)
SPEED = Tag(
    "motor.speed_rpm",
    ("Motor", "Speed"),
    ValueType.DOUBLE,
    unit="rpm",
    description="Measured motor shaft speed",
)
MOTOR_TEMP = Tag(
    "motor.temperature_c",
    ("Motor", "Temperature"),
    ValueType.DOUBLE,
    unit="degC",
    description="Motor winding/frame temperature (D-15)",
)
MOTOR_CURRENT = Tag(
    "motor.current_a",
    ("Motor", "Current"),
    ValueType.DOUBLE,
    unit="A",
    description="Drive output current (RMS), as reported by the VFD (D-04)",
)
LEVEL_LOW = Tag(
    "hopper.level_low",
    ("Hopper", "LevelLow"),
    ValueType.BOOLEAN,
    description="Low level switch; True = material present at switch",
)
LEVEL_HIGH = Tag(
    "hopper.level_high",
    ("Hopper", "LevelHigh"),
    ValueType.BOOLEAN,
    description="High level switch; True = material present at switch",
)
HOPPER_WEIGHT = Tag(
    "hopper.weight_kg",
    ("Hopper", "Weight"),
    ValueType.DOUBLE,
    unit="kg",
    description="Net material mass in the hopper from its load cell (D-03)",
    requires="hopper_load_cell",
)
VIB_SAMPLE_RATE = Tag(
    "vibration.sample_rate_hz",
    ("Vibration", "SampleRate"),
    ValueType.DOUBLE,
    unit="Hz",
    historize=False,
)
VIB_WAVEFORM = Tag(
    "vibration.waveform",
    ("Vibration", "Waveform"),
    ValueType.DOUBLE_ARRAY,
    unit="m/s^2",
    historize=False,
    description="Acceleration block; stored separately, see docs/data.md",
)

FEEDER_TAGS: tuple[Tag, ...] = (
    MACHINE_ID,
    SPEED_SETPOINT,
    SPEED,
    MOTOR_TEMP,
    MOTOR_CURRENT,
    LEVEL_LOW,
    LEVEL_HIGH,
    HOPPER_WEIGHT,
    VIB_SAMPLE_RATE,
    VIB_WAVEFORM,
)

TAGS_BY_KEY: dict[str, Tag] = {t.key: t for t in FEEDER_TAGS}


def tags_for(instruments: frozenset[str]) -> tuple[Tag, ...]:
    """The tags a machine with the given optional instruments exposes."""
    return tuple(t for t in FEEDER_TAGS if t.requires is None or t.requires in instruments)

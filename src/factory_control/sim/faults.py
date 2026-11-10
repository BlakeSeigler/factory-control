"""Fault injection.

Design (docs/fault-injection.md): a fault never reaches into a subsystem's
internals. Each active fault contributes to one ``FaultEffects`` record per step;
subsystems read only that record. Adding a fault therefore never edits physics
code, and the set of "knobs" a fault can turn is explicit and reviewable.

Faults arrive from two sources:
  * a scenario file (config/scenarios/*.yaml): reproducible, scripted runs;
  * the OPC UA Simulation/InjectFault method: interactive, during a live run.

NOT IMPLEMENTED beyond the data model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class FaultKind(StrEnum):
    # process faults (act on physics)
    SCREW_JAM = "screw_jam"  # load torque up, flow down
    HOPPER_BRIDGING = "hopper_bridging"  # flow down with material still in hopper
    WINDING_SHORT = "winding_short"  # extra copper loss -> heating
    FAN_BLOCKED = "fan_blocked"  # thermal resistance up -> heating
    BEARING_WEAR = "bearing_wear"  # bearing defect tones grow
    MISALIGNMENT = "misalignment"  # 2x running-speed component grows
    DRIVE_UNRESPONSIVE = "drive_unresponsive"  # VFD ignores new setpoints
    # sensor faults (act on measurements only)
    SENSOR_STUCK = "sensor_stuck"
    SENSOR_DRIFT = "sensor_drift"
    SWITCH_CHATTER = "switch_chatter"


@dataclass(slots=True)
class FaultEffects:
    """Superposed effect of all active faults on one machine for one step.

    Defaults are the identity (healthy machine).
    """

    load_torque_add_nm: float = 0.0
    fill_factor_mult: float = 1.0
    copper_loss_mult: float = 1.0
    thermal_resistance_mult: float = 1.0
    drive_accepts_setpoints: bool = True
    extra_vibration_tones: list[tuple[float, float]] = field(default_factory=list)  # (Hz, amp)
    sensor_overrides: dict[str, Any] = field(default_factory=dict)  # tag key -> forced value


class ScenarioEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    at_s: float
    machine: str
    fault: FaultKind
    action: Literal["inject", "clear"] = "inject"
    params: dict[str, Any] = {}


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str = ""
    events: list[ScenarioEvent] = []


class FaultManager:
    """Holds active faults for one machine and folds them into ``FaultEffects``."""

    def __init__(self) -> None:
        self.active: dict[FaultKind, dict[str, Any]] = {}

    def inject(self, kind: FaultKind, params: dict[str, Any] | None = None) -> None:
        self.active[kind] = dict(params or {})

    def clear(self, kind: FaultKind | None = None) -> None:
        if kind is None:
            self.active.clear()
        else:
            self.active.pop(kind, None)

    def effects(self, t: float) -> FaultEffects:
        # PLACEHOLDER: faults are recorded (ground truth is visible) but have no effect.
        del t
        return FaultEffects()

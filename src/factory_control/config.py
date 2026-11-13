"""Typed configuration loaded from ``config/line.yaml``.

Every process (simulator, supervisor, dashboard) loads the same file so that
device ids, endpoints and limits cannot drift between them.

Scaffold rule: a field exists only if code reads it today. Model parameters are
added together with the model that uses them (docs/plant-model.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from factory_control.common import tags as T

DEFAULT_CONFIG_PATH = Path("config/line.yaml")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- components ------------------------------------------------------------------------


class OpcUaConfig(_Strict):
    endpoint: str


class MotorConfig(_Strict):
    min_rpm: float = 0.0  # setpoint range enforced by the PLC (D-13)
    max_rpm: float = Field(gt=0)
    initial_rpm: float = 0.0


class MotorThermalConfig(_Strict):
    initial_c: float = 25.0


class VibrationConfig(_Strict):
    sample_rate_hz: float = Field(gt=0)
    block_size: int = Field(gt=0)


class HopperConfig(_Strict):
    capacity_kg: float = Field(gt=0)
    low_switch_kg: float = Field(ge=0)
    high_switch_kg: float = Field(gt=0)
    initial_kg: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> HopperConfig:
        if not (self.low_switch_kg < self.high_switch_kg <= self.capacity_kg):
            raise ValueError("require low_switch_kg < high_switch_kg <= capacity_kg")
        return self


class BarrelConfig(_Strict):
    initial_c: float = 25.0
    setpoint_c: float  # initial barrel temperature setpoint
    min_setpoint_c: float = 0.0  # setpoint range enforced by the PLC (D-13)
    max_setpoint_c: float

    @model_validator(mode="after")
    def _in_range(self) -> BarrelConfig:
        if not (self.min_setpoint_c <= self.setpoint_c <= self.max_setpoint_c):
            raise ValueError("require min_setpoint_c <= setpoint_c <= max_setpoint_c")
        return self


class BathConfig(_Strict):
    initial_c: float = 20.0


# --- devices ---------------------------------------------------------------------------


class _DeviceBase(_Strict):
    id: str
    opcua: OpcUaConfig

    @property
    def tags(self) -> tuple[T.Tag, ...]:
        """Tags this device's PLC exposes (common/tags.py)."""
        return T.DEVICE_TYPES[self.type].tags  # type: ignore[attr-defined]


class ShredderConfig(_DeviceBase):
    type: Literal["shredder"]
    hopper: HopperConfig  # weighed: load cell decided (D-03)
    motor: MotorConfig
    motor_thermal: MotorThermalConfig
    vibration: VibrationConfig


class ExtruderConfig(_DeviceBase):
    type: Literal["extruder"]
    hopper: HopperConfig
    motor: MotorConfig
    motor_thermal: MotorThermalConfig
    vibration: VibrationConfig
    barrel: BarrelConfig


class WaterBathConfig(_DeviceBase):
    type: Literal["water_bath"]
    bath: BathConfig


class PelletizerConfig(_DeviceBase):
    type: Literal["pelletizer"]
    motor: MotorConfig
    motor_thermal: MotorThermalConfig


DeviceConfig = Annotated[
    ShredderConfig | ExtruderConfig | WaterBathConfig | PelletizerConfig,
    Field(discriminator="type"),
]


# --- line / simulator ------------------------------------------------------------------


class LineConfig(_Strict):
    name: str
    # Upstream -> downstream; validated against the fixed line (D-01) so a typo cannot
    # silently reorder the material flow.
    material_path: list[str]


class SimConfig(_Strict):
    physics_dt_s: float = Field(gt=0)
    publish_period_s: float = Field(gt=0)
    time_scale: float = Field(gt=0, default=1.0)
    seed: int = 0


# --- supervisor / dashboard ------------------------------------------------------------


class ControlConfig(_Strict):
    mode: Literal["manual", "baseline", "mpc"] = "manual"
    period_s: float = Field(gt=0, default=1.0)


class SupervisorConfig(_Strict):
    db_path: Path
    subscription_period_ms: int = Field(gt=0)
    historian_flush_period_s: float = Field(gt=0)
    control: ControlConfig


class DashboardConfig(_Strict):
    host: str = "127.0.0.1"
    port: int = 8000
    default_window_s: float = 600.0


# --- root ------------------------------------------------------------------------------

LINE_TYPES = ["shredder", "extruder", "water_bath", "pelletizer"]


class AppConfig(_Strict):
    line: LineConfig
    sim: SimConfig
    devices: list[DeviceConfig]
    supervisor: SupervisorConfig
    dashboard: DashboardConfig

    @model_validator(mode="after")
    def _consistent(self) -> AppConfig:
        ids = [d.id for d in self.devices]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate device ids: {ids}")
        if sorted(ids) != sorted(self.line.material_path):
            raise ValueError("line.material_path must list exactly the configured devices")
        types = [self.device(i).type for i in self.line.material_path]
        if types != LINE_TYPES:
            raise ValueError(f"material path must be {LINE_TYPES} by type, got {types}")
        if len({d.opcua.endpoint for d in self.devices}) != len(self.devices):
            raise ValueError("each device needs its own OPC UA endpoint")
        return self

    def device(self, device_id: str) -> DeviceConfig:
        for d in self.devices:
            if d.id == device_id:
                return d
        raise KeyError(device_id)


def load_yaml[M: BaseModel](model: type[M], path: Path | str) -> M:
    with open(path) as f:
        return model.model_validate(yaml.safe_load(f))


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> AppConfig:
    return load_yaml(AppConfig, path)

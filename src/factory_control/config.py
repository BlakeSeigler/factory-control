"""Typed configuration loaded from ``config/line.yaml``.

Every process (simulator, supervisor, dashboard) loads the same file so that
device ids, endpoints and parameters cannot drift between them.

Devices are a discriminated union on ``type``: each device type has its own
config class, so a shredder cannot be configured with a barrel by mistake.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG_PATH = Path("config/line.yaml")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- reusable components --------------------------------------------------------------


class OpcUaConfig(_Strict):
    endpoint: str


class MotorConfig(_Strict):
    rated_rpm: float
    min_rpm: float = 0.0
    max_rpm: float
    time_constant_s: float = Field(gt=0)
    max_accel_rpm_s: float = Field(gt=0)
    initial_rpm: float = 0.0


class GearboxConfig(_Strict):
    ratio: float = Field(gt=0)  # motor rpm / driven-shaft rpm


class MotorThermalConfig(_Strict):
    ambient_c: float = 25.0
    initial_c: float = 25.0


class VibrationConfig(_Strict):
    sample_rate_hz: float = Field(gt=0)
    block_size: int = Field(gt=0)


class LoadCellConfig(_Strict):
    """Weighing system under a hopper. Imperfection parameters are placeholders (D-21)."""

    resolution_kg: float = Field(gt=0, default=0.01)
    noise_kg: float = Field(ge=0, default=0.0)


class HopperConfig(_Strict):
    capacity_kg: float = Field(gt=0)
    low_switch_kg: float = Field(ge=0)
    high_switch_kg: float = Field(gt=0)
    initial_kg: float = Field(ge=0)
    load_cell: LoadCellConfig | None = None  # None = hopper is not weighed

    @model_validator(mode="after")
    def _ordered(self) -> HopperConfig:
        if not (self.low_switch_kg < self.high_switch_kg <= self.capacity_kg):
            raise ValueError("require low_switch_kg < high_switch_kg <= capacity_kg")
        return self


# --- device-specific components --------------------------------------------------------


class ShredderRotorConfig(_Strict):
    capacity_kg_h_at_rated: float = Field(gt=0)  # placeholder throughput model (D-16)


class ExtruderScrewConfig(_Strict):
    output_kg_h_per_screw_rpm: float = Field(gt=0)  # placeholder throughput model (D-17)


class PidConfig(_Strict):
    kp: float
    ki: float = 0.0  # 1/s
    kd: float = 0.0  # s
    out_min: float = 0.0
    out_max: float = 100.0


class BarrelConfig(_Strict):
    initial_c: float = 25.0
    setpoint_c: float = 200.0
    max_setpoint_c: float = 280.0
    heater_power_kw: float = Field(gt=0)
    min_screw_temp_c: float = 160.0  # cold-start interlock (D-28)
    pid: PidConfig


class BathConfig(_Strict):
    initial_c: float = 20.0


class CutterConfig(_Strict):
    knives: int = Field(gt=0)
    strands: int = Field(gt=0)
    # One motor drives feed rolls and rotor through fixed ratios (D-10, D-19):
    strand_speed_m_min_per_rpm: float = Field(gt=0)  # feed-roll surface speed per motor rpm
    rotor_rpm_per_motor_rpm: float = Field(gt=0, default=1.0)


# --- devices ---------------------------------------------------------------------------


class _DeviceBase(_Strict):
    id: str
    opcua: OpcUaConfig

    @property
    def instruments(self) -> frozenset[str]:
        """Optional instruments fitted; selects optional tags (common/tags.py)."""
        hopper: HopperConfig | None = getattr(self, "hopper", None)
        return frozenset({"hopper_load_cell"} if hopper and hopper.load_cell else ())


class ShredderDeviceConfig(_DeviceBase):
    type: Literal["shredder"]
    hopper: HopperConfig
    motor: MotorConfig
    gearbox: GearboxConfig
    rotor: ShredderRotorConfig
    motor_thermal: MotorThermalConfig
    vibration: VibrationConfig


class ExtruderDeviceConfig(_DeviceBase):
    type: Literal["extruder"]
    hopper: HopperConfig
    motor: MotorConfig
    gearbox: GearboxConfig
    screw: ExtruderScrewConfig
    barrel: BarrelConfig
    motor_thermal: MotorThermalConfig
    vibration: VibrationConfig


class WaterBathDeviceConfig(_DeviceBase):
    type: Literal["water_bath"]
    bath: BathConfig


class PelletizerDeviceConfig(_DeviceBase):
    type: Literal["pelletizer"]
    motor: MotorConfig
    cutter: CutterConfig


DeviceConfig = Annotated[
    ShredderDeviceConfig | ExtruderDeviceConfig | WaterBathDeviceConfig | PelletizerDeviceConfig,
    Field(discriminator="type"),
]


# --- line / sim ------------------------------------------------------------------------


class LineConfig(_Strict):
    name: str
    # Upstream -> downstream. The line in this project is fixed (D-01); the list is
    # validated against it so that a config typo cannot silently reorder physics.
    material_path: list[str]


class MaterialConfig(_Strict):
    """Placeholder material properties for the recycled feed (D-25)."""

    solid_density_kg_m3: float = 950.0
    melt_cp_kj_kg_k: float = 2.0


class RefillConfig(_Strict):
    """Batch refill of the first hopper (D-02).

    When the first hopper's LOW switch uncovers, a batch of ``batch_kg`` is
    requested; it starts pouring after ``response_delay_s`` at ``pour_rate_kg_h``.
    """

    batch_kg: float = Field(gt=0)
    response_delay_s: float = Field(ge=0)
    pour_rate_kg_h: float = Field(gt=0)


class SimConfig(_Strict):
    physics_dt_s: float = Field(gt=0)
    publish_period_s: float = Field(gt=0)
    time_scale: float = Field(gt=0, default=1.0)
    seed: int = 0
    material: MaterialConfig = MaterialConfig()
    refill: RefillConfig


# --- supervisor ------------------------------------------------------------------------


class SetpointTrackingConfig(_Strict):
    deadband_rpm: float
    min_step_rpm: float
    timeout_s: float


class OvertempConfig(_Strict):
    warn_c: float
    alarm_c: float
    hysteresis_c: float


class VibrationAnalyzerConfig(_Strict):
    baseline_blocks: int
    threshold_sigma: float


class AnalyzerConfig(_Strict):
    setpoint_tracking: SetpointTrackingConfig
    overtemp: OvertempConfig
    vibration: VibrationAnalyzerConfig


class ControlConfig(_Strict):
    mode: Literal["manual", "baseline", "mpc"] = "manual"
    period_s: float = Field(gt=0, default=1.0)


class SupervisorConfig(_Strict):
    db_path: Path
    subscription_period_ms: int = Field(gt=0)
    historian_flush_period_s: float = Field(gt=0)
    analyzer: AnalyzerConfig
    control: ControlConfig


class DashboardConfig(_Strict):
    host: str = "127.0.0.1"
    port: int = 8000
    default_window_s: float = 600.0


# --- root ------------------------------------------------------------------------------

EXPECTED_PATH_TYPES = ["shredder", "extruder", "water_bath", "pelletizer"]


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
        if types != EXPECTED_PATH_TYPES:
            raise ValueError(f"material path must be {EXPECTED_PATH_TYPES} by type, got {types}")
        endpoints = [d.opcua.endpoint for d in self.devices]
        if len(set(endpoints)) != len(endpoints):
            raise ValueError("each device needs its own OPC UA endpoint")
        return self

    def device(self, device_id: str) -> DeviceConfig:
        for d in self.devices:
            if d.id == device_id:
                return d
        raise KeyError(device_id)


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> AppConfig:
    with open(path) as f:
        return AppConfig.model_validate(yaml.safe_load(f))

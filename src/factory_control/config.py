"""Typed configuration loaded from ``config/line.yaml``.

Every process (simulator, supervisor, dashboard) loads the same file so that
machine ids, endpoints and parameters cannot drift between them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG_PATH = Path("config/line.yaml")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- machine ---------------------------------------------------------------------------


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
    ratio: float = Field(gt=0)


class ScrewConfig(_Strict):
    displacement_cm3_per_rev: float = Field(gt=0)
    bulk_density_kg_m3: float = Field(gt=0)


class LoadCellConfig(_Strict):
    """Weighing system under a hopper. Imperfection parameters are placeholders (D-26)."""

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


class ThermalConfig(_Strict):
    ambient_c: float = 25.0
    initial_c: float = 25.0


class VibrationConfig(_Strict):
    sample_rate_hz: float = Field(gt=0)
    block_size: int = Field(gt=0)


class MachineConfig(_Strict):
    id: str
    opcua: OpcUaConfig
    motor: MotorConfig
    gearbox: GearboxConfig
    screw: ScrewConfig
    hopper: HopperConfig
    thermal: ThermalConfig
    vibration: VibrationConfig

    @property
    def instruments(self) -> frozenset[str]:
        """Optional instruments fitted to this machine; selects optional tags."""
        return frozenset({"hopper_load_cell"} if self.hopper.load_cell else ())


# --- line / sim ------------------------------------------------------------------------


class LineConfig(_Strict):
    name: str
    topology: Literal["series"]
    machine_order: list[str]


class UpstreamSupplyConfig(_Strict):
    """How material reaches the first machine's hopper (D-02).

    batch_refill: when the first hopper's LOW switch uncovers, a batch of
    ``batch_kg`` is requested; it arrives after ``response_delay_s`` (someone or
    something has to bring it) and pours in at ``pour_rate_kg_h``.
    """

    kind: Literal["batch_refill", "constant", "none"]
    batch_kg: float = Field(gt=0, default=25.0)
    response_delay_s: float = Field(ge=0, default=60.0)
    pour_rate_kg_h: float = Field(gt=0, default=3000.0)
    constant_rate_kg_h: float = Field(ge=0, default=0.0)


class SimConfig(_Strict):
    physics_dt_s: float = Field(gt=0)
    publish_period_s: float = Field(gt=0)
    time_scale: float = Field(gt=0, default=1.0)
    seed: int = 0
    upstream_supply: UpstreamSupplyConfig


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
    mode: Literal["manual", "mpc"] = "manual"
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


class AppConfig(_Strict):
    line: LineConfig
    sim: SimConfig
    machines: list[MachineConfig]
    supervisor: SupervisorConfig
    dashboard: DashboardConfig

    @model_validator(mode="after")
    def _consistent(self) -> AppConfig:
        ids = [m.id for m in self.machines]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate machine ids: {ids}")
        if sorted(ids) != sorted(self.line.machine_order):
            raise ValueError("line.machine_order must list exactly the configured machines")
        return self

    def machine(self, machine_id: str) -> MachineConfig:
        for m in self.machines:
            if m.id == machine_id:
                return m
        raise KeyError(machine_id)


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> AppConfig:
    with open(path) as f:
        return AppConfig.model_validate(yaml.safe_load(f))

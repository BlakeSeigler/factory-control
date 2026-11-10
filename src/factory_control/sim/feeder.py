"""One screw feeder: composes motor, screw, hopper, thermal, vibration and sensors."""

from __future__ import annotations

import numpy as np

from factory_control.config import MachineConfig
from factory_control.sim.faults import FaultManager
from factory_control.sim.hopper import Hopper
from factory_control.sim.motor import Motor
from factory_control.sim.screw import Screw
from factory_control.sim.sensors import Measurements, SensorSuite
from factory_control.sim.thermal import MotorThermal
from factory_control.sim.vibration import VibrationSynth


class Feeder:
    def __init__(self, cfg: MachineConfig, rng: np.random.Generator) -> None:
        self.cfg = cfg
        self.id = cfg.id
        self.motor = Motor(cfg.motor)
        self.screw = Screw(cfg.screw)
        self.hopper = Hopper(cfg.hopper)
        self.thermal = MotorThermal(cfg.thermal)
        self.vibration = VibrationSynth(cfg.vibration, rng)
        self.sensors = SensorSuite(cfg.hopper)
        self.faults = FaultManager()

    def command_speed(self, setpoint_rpm: float) -> float:
        """Setpoint from the OPC UA server. Returns the value actually applied."""
        return self.motor.command(setpoint_rpm)

    def step(self, t: float, dt: float, inflow_kg_s: float) -> float:
        """Advance one physics step. Returns discharged mass flow (kg/s)."""
        fx = self.faults.effects(t)
        screw_rpm = self.motor.state.speed_rpm / self.cfg.gearbox.ratio
        out = self.screw.step(screw_rpm, self.hopper.state.mass_kg)
        load = out.load_torque_nm + fx.load_torque_add_nm
        self.motor.step(dt, load_torque_nm=load)
        self.thermal.step(dt, self.motor.state.speed_rpm, load)
        return self.hopper.step(dt, inflow_kg_s, out.mass_flow_kg_s)

    def measure(self) -> Measurements:
        return self.sensors.measure(
            setpoint_rpm=self.motor.state.setpoint_rpm,
            speed_rpm=self.motor.state.speed_rpm,
            temperature_c=self.thermal.state.temperature_c,
            hopper_mass_kg=self.hopper.state.mass_kg,
        )

    def vibration_block(self) -> np.ndarray:
        return self.vibration.next_block(self.motor.state.speed_rpm)

"""An instrumented motor drive: motor + motor thermal model + their sensor readings.

Used by every motorized device (shredder, extruder, pelletizer) so the motor
wiring and the speed/current/temperature readings exist in one place.
"""

from __future__ import annotations

from typing import Any

from factory_control.common import tags as T
from factory_control.config import MotorConfig, MotorThermalConfig
from factory_control.sim.components.motor import Motor
from factory_control.sim.components.motor_thermal import MotorThermal


class Drive:
    def __init__(self, motor: MotorConfig, thermal: MotorThermalConfig) -> None:
        self.motor = Motor(motor)
        self.thermal = MotorThermal(thermal)

    def step(self, dt: float, load_torque_nm: float = 0.0) -> None:
        self.motor.step(dt, load_torque_nm)
        self.thermal.step(dt, self.motor.state.speed_rpm, self.motor.state.current_a)

    def measure(self) -> dict[str, Any]:
        s = self.motor.state
        return {
            T.SPEED.key: s.speed_rpm,
            T.MOTOR_CURRENT.key: s.current_a,
            T.MOTOR_TEMP.key: self.thermal.state.temperature_c,
        }

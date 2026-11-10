import math

from factory_control.config import MotorConfig
from factory_control.sim.motor import Motor

CFG = MotorConfig(
    rated_rpm=1750, max_rpm=1800, time_constant_s=0.8, max_accel_rpm_s=600, initial_rpm=0
)


def run(motor: Motor, seconds: float, dt: float = 0.01) -> None:
    for _ in range(round(seconds / dt)):
        motor.step(dt)


def test_setpoint_is_clamped():
    m = Motor(CFG)
    assert m.command(5000) == 1800
    assert m.command(-5) == 0


def test_acceleration_is_rate_limited():
    m = Motor(CFG)
    m.command(1800)
    run(m, 1.0)
    assert m.state.speed_rpm <= 600 + 1e-6


def test_converges_first_order_once_off_the_rate_limit():
    m = Motor(CFG)
    m.state.speed_rpm = 1000.0
    m.command(1100)  # 100 rpm step: initial rate 125 rpm/s < limit, pure first order
    run(m, CFG.time_constant_s)
    expected = 1100 - 100 * math.exp(-1)
    assert abs(m.state.speed_rpm - expected) < 1.0

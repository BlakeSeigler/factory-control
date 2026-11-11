from factory_control.config import PidConfig
from factory_control.plc.pid import Pid


def simulate(pid: Pid, seconds: float, dt: float = 0.1, tau: float = 20.0, gain: float = 2.0):
    """First-order plant: dy/dt = (gain * u - y) / tau."""
    y = 0.0
    for _ in range(round(seconds / dt)):
        u = pid.update(y, dt)
        y += dt * (gain * u - y) / tau
    return y


def test_pi_removes_steady_state_error():
    pid = Pid(PidConfig(kp=0.5, ki=0.05, out_min=0, out_max=100), setpoint=50.0)
    assert abs(simulate(pid, 600) - 50.0) < 0.5


def test_output_is_clamped():
    pid = Pid(PidConfig(kp=100.0, out_min=0, out_max=100), setpoint=1000.0)
    assert pid.update(0.0, 0.1) == 100.0
    assert Pid(PidConfig(kp=100.0), setpoint=-1000.0).update(0.0, 0.1) == 0.0


def test_anti_windup_stops_integration_while_saturated():
    pid = Pid(PidConfig(kp=1.0, ki=1.0, out_min=0, out_max=10), setpoint=100.0)
    for _ in range(1000):
        pid.update(0.0, 0.1)  # error 100 forever, output pinned at 10
    assert pid.integral == 0.0


def test_no_derivative_kick_on_setpoint_step():
    pid = Pid(PidConfig(kp=0.0, kd=10.0, out_min=-1e9, out_max=1e9), setpoint=0.0)
    pid.update(5.0, 0.1)
    pid.setpoint = 500.0
    assert pid.update(5.0, 0.1) == 0.0  # measurement unchanged -> no derivative action

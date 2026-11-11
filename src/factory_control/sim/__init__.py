"""Plant model of the recycling line. Pure Python/numpy; no OPC UA, no control logic.

    components/   reusable physics: motor/drive, motor thermal, hopper, sensors, vibration
    devices/      one plant model per device type, composed from components
    line.py       couples devices by material flow; batch refill of the first hopper
    faults.py     fault injection

Control logic (barrel PID, interlocks) lives in ``plc/``, not here: the plant only
has actuators and sensors, exactly like real equipment (docs/architecture.md).
Process faults act on physics; sensor faults act only in the measurement layer.
"""

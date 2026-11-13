"""Shredder PLC.

NOT IMPLEMENTED (D-27): overload auto-reverse. On an overload the PLC stops,
reverses the rotor briefly to free the jam, then resumes; after N failed attempts
it stops with a fault. While this runs, speed deliberately does not follow the
setpoint, which is why publishing the PLC's state is open (D-07).
"""

from __future__ import annotations

from factory_control.plc.base import DevicePLC


class ShredderPLC(DevicePLC):
    pass

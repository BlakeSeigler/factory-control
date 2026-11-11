"""Shredder PLC.

TODO(D-27): overload auto-reverse, standard on shredders. On an overload (current
above limit or rotor stalled), the PLC stops, reverses the rotor for a few
seconds to free the jam, then resumes; after N failed attempts it stops with a
fault. While this happens the speed deliberately does not follow the setpoint,
so the supervisor must be told (a state tag, D-07); otherwise Rule 1 raises a
false alarm every time the shredder clears itself.
"""

from __future__ import annotations

from factory_control.plc.base import DevicePLC


class ShredderPLC(DevicePLC):
    pass

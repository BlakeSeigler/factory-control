"""State estimation for supervisory control.

NOT IMPLEMENTED (docs/control.md section 3, D-42). Quantities the controllers need
but no sensor measures directly:

  shredder throughput    -dM/dt of the weighed hopper, valid between refills
  extruder throughput    K_ext_hat * screw speed; K_ext_hat corrected over intervals
                         that start and end at the same extruder-hopper switch state
  extruder hopper mass   dead reckoning (shredder out - extruder out), corrected at
                         switch transitions, bounded by the switch states
"""

from __future__ import annotations

from factory_control.supervisor.state import StateCache


class LineEstimator:
    def update(self, now: float, state: StateCache) -> dict[str, float]:
        raise NotImplementedError("see docs/control.md section 3")

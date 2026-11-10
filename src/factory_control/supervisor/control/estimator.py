"""State estimation: the MPC needs hopper mass, which no sensor measures.

NOT IMPLEMENTED. The only level information is two binary switches per hopper.
Candidate (docs/mpc.md section 4, D-33): integrate the model mass balance
(open-loop prediction, drifts with calibration error K_i) and correct it at
switch transitions, which are exact-level events ("mass crossed 10 kg now").
Between transitions the estimate's uncertainty grows; a Kalman filter makes that
explicit and also estimates the calibration error as an extra state.
"""

from __future__ import annotations

from factory_control.supervisor.state import StateCache


class HopperMassEstimator:
    def update(self, now: float, state: StateCache) -> dict[str, float]:
        raise NotImplementedError("see docs/mpc.md section 4")

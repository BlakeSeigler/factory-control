"""The line: devices coupled by material flow, upstream to downstream.

    refill -> shredder -> extruder -> water bath -> pelletizer -> pellets

Coupling is physical (mass), so it lives here in the simulator, not on the OPC UA
network. Each device still has its own PLC and OPC UA server (plc/), as real
equipment would; the supervisor cannot tell they share a process (D-05).
"""

from __future__ import annotations

import numpy as np

from factory_control.config import AppConfig
from factory_control.sim.clock import SimClock
from factory_control.sim.devices import DevicePlant, build_plant


class BatchRefill:
    """Batch refill of the first hopper by a person (D-02).

    NOT IMPLEMENTED: when the first hopper's LOW switch uncovers, a person brings a
    batch after a random delay. Delay distribution and overflow are deferred.
    """

    def flow_kg_s(self, t: float, first: DevicePlant) -> float:
        del t, first
        return 0.0


class Line:
    def __init__(self, cfg: AppConfig, clock: SimClock) -> None:
        self.path = cfg.line.material_path
        self.clock = clock
        rng = np.random.default_rng(cfg.sim.seed)
        self.devices: dict[str, DevicePlant] = {
            did: build_plant(cfg.device(did), np.random.default_rng(rng.integers(2**63)))
            for did in self.path
        }
        self.refill = BatchRefill()

    def step(self, dt: float) -> None:
        t = self.clock.now
        flow = self.refill.flow_kg_s(t, self.devices[self.path[0]])
        for did in self.path:
            flow = self.devices[did].step(t, dt, inflow_kg_s=flow)
        self.clock.advance(dt)

"""The line: devices coupled by material flow, upstream to downstream.

    batch refill -> shredder -> extruder -> water bath -> pelletizer -> pellets

Coupling is physical (mass), so it lives here in the simulator, not on the OPC UA
network. Each device still has its own PLC and OPC UA server (plc/), exactly as
real equipment would; the supervisor cannot tell they share a process (D-05).
"""

from __future__ import annotations

import numpy as np

from factory_control.config import AppConfig, RefillConfig
from factory_control.sim.clock import SimClock
from factory_control.sim.devices import DevicePlant, build_device
from factory_control.sim.devices.shredder import ShredderPlant


class BatchRefill:
    """Batch refill of the first hopper (D-02).

    PLACEHOLDER: never delivers. To implement: when the shredder's LOW switch
    uncovers and no batch is pending, a person brings a batch of ``batch_kg``
    after a random delay (mean ``response_delay_mean_s``), which pours at
    ``pour_rate_kg_h``. Open: delay distribution; overflow handling.
    """

    def __init__(self, cfg: RefillConfig) -> None:
        self.cfg = cfg
        self.delivered_kg = 0.0

    def flow_kg_s(self, t: float, first: ShredderPlant) -> float:
        del t, first
        return 0.0


class Line:
    def __init__(self, cfg: AppConfig, clock: SimClock) -> None:
        self.cfg = cfg
        self.clock = clock
        rng = np.random.default_rng(cfg.sim.seed)
        self.devices: dict[str, DevicePlant] = {
            did: build_device(
                cfg.device(did), cfg.sim.material, np.random.default_rng(rng.integers(2**63))
            )
            for did in cfg.line.material_path
        }
        first = self.devices[cfg.line.material_path[0]]
        assert isinstance(first, ShredderPlant)
        self.first: ShredderPlant = first
        self.refill = BatchRefill(cfg.sim.refill)
        self.output_kg_s = 0.0  # pellets leaving the line; ground truth only

    def step(self, dt: float) -> None:
        t = self.clock.now
        flow = self.refill.flow_kg_s(t, self.first)
        for did in self.cfg.line.material_path:
            flow = self.devices[did].step(t, dt, inflow_kg_s=flow)
        self.output_kg_s = flow
        self.clock.advance(dt)

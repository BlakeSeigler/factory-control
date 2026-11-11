"""The line: feeders coupled in series by material flow.

    supply --> [feeder_1 hopper -> screw] --> [feeder_2 hopper -> screw] --> process

Coupling is physical (mass), so it lives here in the simulator, not on the OPC UA
network. Each feeder still gets its own OPC UA server (machine/), exactly as two
real machines would; the supervisor cannot tell they share a process (D-05).
"""

from __future__ import annotations

import numpy as np

from factory_control.config import AppConfig, UpstreamSupplyConfig
from factory_control.sim.clock import SimClock
from factory_control.sim.feeder import Feeder


class UpstreamSupply:
    """Material source for the first hopper (D-02).

    PLACEHOLDER: always off. ``batch_refill`` must model: LOW switch of the first
    hopper uncovers -> after ``response_delay_s`` a batch of ``batch_kg`` pours in
    at ``pour_rate_kg_h``. Whether the delay is fixed or random (a person
    responding) and what happens if the batch would overflow are open (D-02).
    """

    def __init__(self, cfg: UpstreamSupplyConfig) -> None:
        self.cfg = cfg

    def flow_kg_s(self, first: Feeder) -> float:
        del first
        return 0.0


class Line:
    def __init__(self, cfg: AppConfig, clock: SimClock) -> None:
        self.cfg = cfg
        self.clock = clock
        rng = np.random.default_rng(cfg.sim.seed)
        self.feeders: dict[str, Feeder] = {
            mid: Feeder(cfg.machine(mid), np.random.default_rng(rng.integers(2**63)))
            for mid in cfg.line.machine_order
        }
        self.supply = UpstreamSupply(cfg.sim.upstream_supply)
        self.line_output_kg_s = 0.0  # ground truth only; not exposed as a sensor (D-03)

    def step(self, dt: float) -> None:
        order = self.cfg.line.machine_order
        flow = self.supply.flow_kg_s(self.feeders[order[0]])
        for mid in order:
            flow = self.feeders[mid].step(self.clock.now, dt, inflow_kg_s=flow)
        self.line_output_kg_s = flow
        self.clock.advance(dt)

"""OPC UA client for one machine: connect, subscribe, reconnect, write setpoints.

One ``MachineClient`` per machine, each with its own session, so a dead machine
cannot stall the other (requirement: separate server and connection per machine).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from asyncua import Client, Node, ua
from asyncua.common.subscription import DataChangeNotif

from factory_control.common import tags as T
from factory_control.common.messages import Sample
from factory_control.config import MachineConfig
from factory_control.supervisor.bus import Bus

log = logging.getLogger(__name__)

GROUND_TRUTH_TAG = "sim.active_faults"
# Server-side lifetime of a session after the client goes silent. Short, so a crashed
# supervisor's session (and its subscriptions) is reclaimed quickly by the machine.
SESSION_TIMEOUT_MS = 30_000


class _Handler:
    def __init__(self, machine_id: str, keys: dict[ua.NodeId, str], bus: Bus[Sample]) -> None:
        self.machine_id = machine_id
        self.keys = keys
        self.bus = bus

    def datachange_notification(self, node: Node, val: Any, data: DataChangeNotif) -> None:
        dv = data.monitored_item.Value
        ts = dv.SourceTimestamp or dv.ServerTimestamp
        self.bus.publish(
            Sample(
                machine_id=self.machine_id,
                tag=self.keys[node.nodeid],
                value=val,
                source_ts=ts.timestamp() if ts else 0.0,
                status=dv.StatusCode.value if dv.StatusCode else 0,
            )
        )

    def status_change_notification(self, status: Any) -> None:
        log.warning("%s subscription status change: %s", self.machine_id, status)


class MachineClient:
    def __init__(
        self,
        cfg: MachineConfig,
        bus: Bus[Sample],
        *,
        period_ms: int,
        include_ground_truth: bool = True,
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.period_ms = period_ms
        self.include_ground_truth = include_ground_truth
        self.connected = asyncio.Event()
        self._client: Client | None = None
        self._nodes: dict[str, Node] = {}

    @property
    def machine_id(self) -> str:
        return self.cfg.id

    async def run(self, stop: asyncio.Event) -> None:
        """Connect and stay connected until ``stop`` is set, with capped backoff."""
        backoff = 1.0
        while not stop.is_set():
            client = Client(self.cfg.opcua.endpoint, timeout=4)
            client.session_timeout = SESSION_TIMEOUT_MS
            try:
                async with client:
                    self._client = client
                    await self._subscribe(client)
                    self.connected.set()
                    log.info("%s connected to %s", self.machine_id, self.cfg.opcua.endpoint)
                    backoff = 1.0
                    while not stop.is_set():
                        await client.check_connection()
                        await asyncio.sleep(1.0)
            except (OSError, TimeoutError, ua.UaError) as e:
                log.warning(
                    "%s connection problem: %r; retry in %.0fs", self.machine_id, e, backoff
                )
            finally:
                self.connected.clear()
                self._client = None
                self._nodes.clear()
            if not stop.is_set():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _subscribe(self, client: Client) -> None:
        ns = await client.get_namespace_index(T.FEEDER_NS_URI)
        keys: dict[ua.NodeId, str] = {}
        for tag in T.FEEDER_TAGS:
            path = [f"{ns}:{T.ROOT_OBJECT}", *(f"{ns}:{p}" for p in tag.path)]
            node = await client.nodes.objects.get_child(path)
            self._nodes[tag.key] = node
            keys[node.nodeid] = tag.key

        if self.include_ground_truth:
            sim_ns = await client.get_namespace_index(T.SIM_NS_URI)
            node = await client.nodes.objects.get_child(
                [f"{sim_ns}:{T.SIM_OBJECT}", f"{sim_ns}:ActiveFaults"]
            )
            keys[node.nodeid] = GROUND_TRUTH_TAG

        handler = _Handler(self.machine_id, keys, self.bus)
        sub = await client.create_subscription(self.period_ms, handler)
        # TODO(D-06): per-tag sampling intervals, queue sizes and deadbands.
        await sub.subscribe_data_change(list(client.get_node(n) for n in keys))

    async def write_setpoint(self, rpm: float) -> None:
        if self._client is None:
            raise ConnectionError(f"{self.machine_id} is not connected")
        node = self._nodes[T.SPEED_SETPOINT.key]
        await node.write_value(ua.Variant(float(rpm), ua.VariantType.Double))

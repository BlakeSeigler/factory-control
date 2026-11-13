"""OPC UA client side: one ``DeviceClient`` (one session) per device PLC.

An outage of one PLC therefore cannot stall the others. The helpers at the top
are shared with the CLI so connection settings and write rules exist once.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from asyncua import Client, Node, ua
from asyncua.common.subscription import DataChangeNotif

from factory_control.common import tags as T
from factory_control.common.messages import Sample
from factory_control.config import DeviceConfig
from factory_control.supervisor.bus import Bus

log = logging.getLogger(__name__)

# Server-side lifetime of a session after the client goes silent. Short, so a crashed
# supervisor's session (and its subscriptions) is reclaimed quickly by the PLC.
SESSION_TIMEOUT_MS = 30_000

_VARIANT = {T.ValueType.DOUBLE: ua.VariantType.Double, T.ValueType.BOOLEAN: ua.VariantType.Boolean}


def make_client(endpoint: str) -> Client:
    client = Client(endpoint, timeout=4)
    client.session_timeout = SESSION_TIMEOUT_MS
    return client


async def resolve_tag_nodes(client: Client, device: DeviceConfig) -> dict[str, Node]:
    """Node for every tag of the device, keyed by tag key."""
    ns = await client.get_namespace_index(T.DEVICE_NS_URI)
    root = f"{ns}:{T.DEVICE_TYPES[device.type].root}"
    return {
        t.key: await client.nodes.objects.get_child([root, *(f"{ns}:{p}" for p in t.path)])
        for t in device.tags
    }


async def resolve_sim_object(client: Client) -> tuple[Node, int]:
    """The sim-only Simulation object and its namespace index (D-14)."""
    ns = await client.get_namespace_index(T.SIM_NS_URI)
    return await client.nodes.objects.get_child([f"{ns}:{T.SIM_OBJECT}"]), ns


async def write_tag(node: Node, tag: T.Tag, value: float | bool) -> None:
    """Write a setpoint. The PLC rejects out-of-range values: raises
    ``ua.uaerrors.BadOutOfRange`` (a ``UaStatusCodeError``) (D-13)."""
    if not tag.writable:
        raise ValueError(f"{tag.key} is not writable")
    await node.write_value(ua.Variant(value, _VARIANT[tag.vtype]))


class _Handler:
    def __init__(self, device_id: str, keys: dict[ua.NodeId, str], bus: Bus[Sample]) -> None:
        self.device_id = device_id
        self.keys = keys
        self.bus = bus

    def datachange_notification(self, node: Node, val: Any, data: DataChangeNotif) -> None:
        dv = data.monitored_item.Value
        ts = dv.SourceTimestamp or dv.ServerTimestamp
        self.bus.publish(
            Sample(
                device_id=self.device_id,
                tag=self.keys[node.nodeid],
                value=val,
                source_ts=ts.timestamp() if ts else 0.0,
                status=dv.StatusCode.value if dv.StatusCode else 0,
            )
        )

    def status_change_notification(self, status: Any) -> None:
        log.warning("%s subscription status change: %s", self.device_id, status)


class DeviceClient:
    def __init__(self, cfg: DeviceConfig, bus: Bus[Sample], *, period_ms: int) -> None:
        self.cfg = cfg
        self.bus = bus
        self.period_ms = period_ms
        self.connected = asyncio.Event()
        self._nodes: dict[str, Node] = {}

    @property
    def device_id(self) -> str:
        return self.cfg.id

    async def run(self, stop: asyncio.Event) -> None:
        """Connect and stay connected until ``stop`` is set, with capped backoff."""
        backoff = 1.0
        while not stop.is_set():
            client = make_client(self.cfg.opcua.endpoint)
            try:
                async with client:
                    await self._subscribe(client)
                    self.connected.set()
                    log.info("%s connected to %s", self.device_id, self.cfg.opcua.endpoint)
                    backoff = 1.0
                    while not stop.is_set():
                        await client.check_connection()
                        await asyncio.sleep(1.0)
            except (OSError, TimeoutError, ua.UaError) as e:
                log.warning("%s connection problem: %r; retry in %.0fs", self.device_id, e, backoff)
            finally:
                self.connected.clear()
                self._nodes.clear()
            if not stop.is_set():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _subscribe(self, client: Client) -> None:
        self._nodes = await resolve_tag_nodes(client, self.cfg)
        sim, ns = await resolve_sim_object(client)
        truth_node = await sim.get_child(f"{ns}:{T.SIM_ACTIVE_FAULTS}")
        keys = {n.nodeid: key for key, n in self._nodes.items()}
        keys[truth_node.nodeid] = T.GROUND_TRUTH_KEY
        sub = await client.create_subscription(
            self.period_ms, _Handler(self.device_id, keys, self.bus)
        )
        # TODO(D-11): per-tag sampling intervals, queue sizes and deadbands.
        await sub.subscribe_data_change([*self._nodes.values(), truth_node])

    async def write(self, tag_key: str, value: float) -> None:
        if not self.connected.is_set():
            raise ConnectionError(f"{self.device_id} is not connected")
        await write_tag(self._nodes[tag_key], T.ALL_TAGS[tag_key], value)

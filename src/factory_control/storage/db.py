"""Thin synchronous SQLite access layer.

Synchronous on purpose: sqlite3 calls are short, and async callers wrap them in
``asyncio.to_thread``. No ORM; the schema is small and the SQL is the documentation.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from importlib import resources
from pathlib import Path

from factory_control.common.messages import AlarmEvent, SetpointCommand

SampleRow = tuple[float, str, str, float, int]  # ts, device_id, tag, value, status
TruthRow = tuple[float, str, str]  # ts, device_id, active_faults JSON


class Database:
    def __init__(self, path: Path | str, *, readonly: bool = False) -> None:
        self.path = Path(path)
        if readonly:
            uri = f"file:{self.path}?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.conn.close()

    # -- writer -------------------------------------------------------------------------

    def init_schema(self) -> None:
        sql = resources.files("factory_control.storage").joinpath("schema.sql").read_text()
        self.conn.executescript(sql)

    def upsert_devices(self, devices: Iterable[tuple[str, str, str]]) -> None:
        """(id, type, endpoint) rows."""
        with self.conn:
            self.conn.executemany(
                "INSERT INTO device (id, type, endpoint) VALUES (?, ?, ?) ON CONFLICT(id) "
                "DO UPDATE SET type = excluded.type, endpoint = excluded.endpoint",
                list(devices),
            )

    def insert_batch(self, samples: list[SampleRow], truth: list[TruthRow]) -> None:
        """Samples and ground-truth transitions in one transaction."""
        with self.conn:
            self.conn.executemany(
                "INSERT INTO sample (ts, device_id, tag, value, status) VALUES (?, ?, ?, ?, ?)",
                samples,
            )
            self.conn.executemany(
                "INSERT INTO sim_ground_truth (ts, device_id, active_faults) VALUES (?, ?, ?)",
                truth,
            )

    def insert_setpoint_commands(self, cmds: list[SetpointCommand]) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT INTO setpoint_command (ts, device_id, tag, value, source) "
                "VALUES (?, ?, ?, ?, ?)",
                [(c.ts, c.device_id, c.tag, c.value, c.source) for c in cmds],
            )

    def insert_alarm_event(self, ev: AlarmEvent) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO alarm_event (ts, device_id, rule, severity, transition, message, "
                "details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ev.ts, ev.device_id, ev.rule, ev.severity.value, ev.transition.value,
                 ev.message, json.dumps(ev.details)),
            )  # fmt: skip

    # -- reader -------------------------------------------------------------------------

    def series(self, device_id: str, tag: str, since: float) -> list[tuple[float, float]]:
        cur = self.conn.execute(
            "SELECT ts, value FROM sample WHERE device_id = ? AND tag = ? AND ts >= ? ORDER BY ts",
            (device_id, tag, since),
        )
        return cur.fetchall()

    def latest_ts(self, device_ids: list[str], tag: str) -> float | None:
        """Newest sample time of ``tag`` across devices (answered by the index)."""
        latest = [
            self.conn.execute(
                "SELECT MAX(ts) FROM sample WHERE device_id = ? AND tag = ?", (did, tag)
            ).fetchone()[0]
            for did in device_ids
        ]
        return max((t for t in latest if t is not None), default=None)

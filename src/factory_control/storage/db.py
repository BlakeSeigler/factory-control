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

    def insert_samples(self, rows: list[SampleRow]) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT INTO sample (ts, device_id, tag, value, status) VALUES (?, ?, ?, ?, ?)",
                rows,
            )

    def insert_setpoint_command(self, cmd: SetpointCommand) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO setpoint_command (ts, device_id, tag, value, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (cmd.ts, cmd.device_id, cmd.tag, cmd.value, cmd.source),
            )

    def insert_alarm_event(self, ev: AlarmEvent) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO alarm_event (ts, device_id, rule, severity, transition, message, "
                "details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ev.ts,
                    ev.device_id,
                    ev.rule,
                    ev.severity.value,
                    ev.transition.value,
                    ev.message,
                    json.dumps(ev.details),
                ),
            )

    def insert_ground_truth(self, ts: float, device_id: str, active_faults_json: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO sim_ground_truth (ts, device_id, active_faults) VALUES (?, ?, ?)",
                (ts, device_id, active_faults_json),
            )

    # -- reader -------------------------------------------------------------------------

    def device_ids(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT id FROM device ORDER BY id")]

    def series(self, device_id: str, tag: str, since: float) -> list[tuple[float, float]]:
        cur = self.conn.execute(
            "SELECT ts, value FROM sample WHERE device_id = ? AND tag = ? AND ts >= ? ORDER BY ts",
            (device_id, tag, since),
        )
        return cur.fetchall()

    def latest_ts(self) -> float | None:
        row = self.conn.execute("SELECT MAX(ts) FROM sample").fetchone()
        return row[0] if row else None

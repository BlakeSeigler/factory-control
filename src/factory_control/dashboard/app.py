"""Placeholder dashboard: one page, one chart (motor speed of every motorized device).

Reads SQLite directly in read-only mode; it never talks to the PLCs, so it cannot
issue commands by construction (D-46).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from factory_control.common import tags as T
from factory_control.config import AppConfig
from factory_control.storage.db import Database


def create_app(cfg: AppConfig) -> FastAPI:
    app = FastAPI(title="factory-control dashboard")
    static_dir = Path(str(resources.files("factory_control.dashboard").joinpath("static")))
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    index_html = (static_dir / "index.html").read_text()

    # Devices exposing each historized tag, in line order (stable chart colors).
    devices_by_tag: dict[str, list[str]] = {}
    for did in cfg.line.material_path:
        for tag in cfg.device(did).tags:
            if tag.historize:
                devices_by_tag.setdefault(tag.key, []).append(did)

    db_path = Path(cfg.supervisor.db_path)
    db: Database | None = None  # opened on first use: the supervisor creates the file

    def get_db() -> Database:
        nonlocal db
        if db is None:
            if not db_path.exists():
                raise HTTPException(503, f"historian database {db_path} does not exist yet")
            db = Database(db_path, readonly=True)
        return db

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return index_html

    @app.get("/api/series")
    def series(
        tag: str = Query(T.SPEED.key),
        window_s: float = Query(cfg.dashboard.default_window_s, gt=0, le=86_400),
    ) -> dict:
        if tag not in devices_by_tag:
            raise HTTPException(400, f"unknown or non-historized tag {tag!r}")
        d, devices = get_db(), devices_by_tag[tag]
        out: dict[str, dict[str, list[float]]] = {}
        if (end := d.latest_ts(devices, tag)) is not None:
            for did in devices:
                rows = d.series(did, tag, end - window_s)
                out[did] = {"t": [r[0] for r in rows], "v": [r[1] for r in rows]}
        return {"tag": tag, "unit": T.ALL_TAGS[tag].unit, "series": out}

    return app

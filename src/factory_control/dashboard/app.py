"""Placeholder dashboard: one page, one chart (motor speed of every motorized device).

Reads SQLite directly in read-only mode; it never talks to the PLCs. That keeps the
dashboard incapable of issuing commands by construction (D-46).
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
    db_path = Path(cfg.supervisor.db_path)
    static_dir = Path(str(resources.files("factory_control.dashboard").joinpath("static")))
    index_html = static_dir / "index.html"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def devices_with(tag: str) -> list[str]:
        return [
            did
            for did in cfg.line.material_path
            if any(
                t.key == tag for t in T.tags_for(cfg.device(did).type, cfg.device(did).instruments)
            )
        ]

    def db() -> Database:
        if not db_path.exists():
            raise HTTPException(503, f"historian database {db_path} does not exist yet")
        return Database(db_path, readonly=True)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return index_html.read_text()

    @app.get("/api/series")
    def series(
        tag: str = Query(T.SPEED.key),
        window_s: float = Query(cfg.dashboard.default_window_s, gt=0, le=86_400),
    ) -> dict:
        if tag not in T.ALL_TAGS or not T.ALL_TAGS[tag].historize:
            raise HTTPException(400, f"unknown or non-historized tag {tag!r}")
        d = db()
        try:
            end = d.latest_ts()
            out: dict[str, dict[str, list[float]]] = {}
            if end is not None:
                # Line order, so each device keeps the same color whatever the window.
                for did in devices_with(tag):
                    rows = d.series(did, tag, end - window_s)
                    out[did] = {"t": [r[0] for r in rows], "v": [r[1] for r in rows]}
            return {"tag": tag, "unit": T.ALL_TAGS[tag].unit, "series": out}
        finally:
            d.close()

    return app

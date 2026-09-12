"""FastAPI 应用工厂"""
from __future__ import annotations
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings
from app.lifespan import lifespan
from app.api import health, auth


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings("lite")

    app = FastAPI(
        title="Cashier",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.include_router(health.router)
    app.include_router(auth.router)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index():
            return (static_dir / "index.html").read_text(encoding="utf-8")

    return app


def setup_logging(settings: Settings) -> None:
    from logging.handlers import RotatingFileHandler
    settings.ensure_dirs()
    log_file = settings.logs_dir / "app.log"
    handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root = logging.getLogger()
    root.setLevel(settings.logging.level)
    root.addHandler(handler)

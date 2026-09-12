"""FastAPI 应用工厂"""
from __future__ import annotations
import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.lifespan import lifespan
from app.api import health, auth
from app.api.merchant import products, orders, cashier, categories
from app.api.admin import tenants, licenses
from app.api.dashboard import router as dashboard_router

log = logging.getLogger(__name__)


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

    # CORS: 仅允许同源（本地部署场景允许 localhost）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # 全局异常处理器：避免泄露内部堆栈
    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception):
        log.error(f"未捕获异常: {request.method} {request.url.path}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": "系统内部错误", "code": "internal_error"},
        )

    # Health & Auth
    app.include_router(health.router)
    app.include_router(auth.router)

    # Merchant APIs
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(cashier.router)  # includes /api/v1/merchant/members and /checkout
    app.include_router(categories.router)

    # Admin APIs
    app.include_router(tenants.router)
    app.include_router(licenses.router)

    # Dashboard
    app.include_router(dashboard_router)

    # Static frontend
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index():
            html = (static_dir / "index.html").read_text(encoding="utf-8")
            return HTMLResponse(content=html)

        @app.get("/dashboard", response_class=HTMLResponse)
        async def dashboard():
            html = (static_dir / "dashboard.html").read_text(encoding="utf-8")
            return HTMLResponse(content=html)

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

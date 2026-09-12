"""FastAPI 启动/关闭钩子"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.bootstrap import ensure_admin
from app.infra.db.engine import init_engine, session_factory
from app.infra.db.write_queue import start_writer
from app.infra.db.migrations import run_migrations
from app.kernel.auth.engine import OfflineAuthEngine
from app.kernel.license.verifier import LicenseVerifier
from app.kernel.license.trial import generate_trial_license

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings

    init_engine(settings)
    run_migrations()
    start_writer()

    app.state.auth = OfflineAuthEngine(
        session_factory=session_factory,
        secret=settings._session_secret,  # type: ignore[attr-defined]
        cfg=settings,
    )

    pwd = ensure_admin(settings, app.state.auth)
    if pwd:
        print("\n" + "=" * 56)
        print("  首次启动：已创建管理员账户")
        print(f"  用户名: admin")
        print(f"  密  码: {pwd}")
        print(f"  已保存: {settings.home / 'data' / 'initial-password.txt'}")
        print("=" * 56 + "\n")

    pub_pem = (settings.secrets_dir / "license_pub.pem").read_bytes()
    verifier = LicenseVerifier(pub_pem, grace_days=settings.license.grace_days)

    if not settings.license_path.exists() and settings.license.allow_trial:
        priv_pem = (settings.secrets_dir / "license_priv.pem").read_bytes()
        generate_trial_license(priv_pem, settings.license_path, days=30)
        log.info("已生成 30 天试用 License")

    result = verifier.verify(settings.license_path)
    app.state.license = result
    log.info("License 状态: %s (%s)", result.status, result.message)

    print(f"✅ Cashier 已启动  |  License: {result.status}")
    yield
    log.info("Cashier 关闭")

"""FastAPI 启动/关闭钩子"""
from __future__ import annotations
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.bootstrap import ensure_admin
from app.infra.db.engine import init_engine, session_factory, get_engine
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

    # Seed demo data
    from app.application.product.product_service import ProductService
    from app.application.member.member_service import MemberService
    n_products = ProductService(merchant_id="local").seed_demo_products()
    n_members = MemberService(merchant_id="local").seed_demo_members()
    if n_products:
        log.info(f"Seeded {n_products} demo products")
    if n_members:
        log.info(f"Seeded {n_members} demo members")

    print(f"✅ Cashier 已启动  |  License: {result.status}")
    if n_products:
        print(f"  已写入 {n_products} 个示例商品")
    if n_members:
        print(f"  已写入 {n_members} 个示例会员")

    # 启动时间戳（用于运行时长统计）
    app.state.started_at = time.time()

    yield

    # ========== 优雅关闭 ==========
    log.info("Cashier 正在关闭...")

    # 1. 停止接受新请求后，关闭数据库连接池
    try:
        engine = get_engine()
        engine.dispose()
        log.info("已关闭数据库连接池")
    except Exception as e:
        log.warning(f"关闭数据库时出错: {e}")

    elapsed = time.time() - getattr(app.state, 'started_at', time.time())
    log.info(f"Cashier 已关闭 (运行 {elapsed:.1f}s)")

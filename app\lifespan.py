"""FastAPI 启动/关闭钩子"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import ensure_admin
from app.config import Settings
from app.infra.db.engine import get_engine, init_engine, session_factory
from app.infra.db.migrations import run_migrations
from app.kernel.auth.engine import OfflineAuthEngine
from app.kernel.license.trial import generate_trial_license
from app.kernel.license.verifier import LicenseVerifier

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
        print("  用户名: admin")
        print(f"  密  码: {pwd}")
        print(f"  已保存: {settings.home / 'data' / 'initial-password.txt'}")
        print("=" * 56 + "\n")

    pub_pem = (settings.secrets_dir / "license_pub.pem").read_bytes()
    verifier = LicenseVerifier(pub_pem, grace_days=settings.license.grace_days)

    if not settings.license_path.exists() and settings.license.allow_trial:
        priv_pem = (settings.secrets_dir / "license_priv.pem").read_bytes()
        generate_trial_license(priv_pem, settings.license_path, days=30)
        log.info("已生成 30 天试用 License")

    # Seed demo data
    from app.application.member.member_service import MemberService
    from app.application.product.product_service import ProductService

    n_products = ProductService(merchant_id="local").seed_demo_products()
    n_members = MemberService(merchant_id="local").seed_demo_members()
    if n_products:
        log.info(f"Seeded {n_products} demo products")
    if n_members:
        log.info(f"Seeded {n_members} demo members")

    # ── M4: 初始化仓库与原料 ──
    from app.application.inventory.inventory_service import InventoryService
    inv_svc = InventoryService(merchant_id="local")
    wh = inv_svc.init_warehouse(name="主仓库")
    mats = inv_svc.init_raw_materials()
    if wh:
        log.info(f"初始化仓库: {wh.name} ({wh.id})")
    if mats:
        log.info(f"初始化 {len(mats)} 个示例原料")

    # ── License 验签 & 写入 tenants 表 ──
    from app.infra.db.models import Tenant

    result = verifier.verify(settings.license_path)
    app.state.license = result
    log.info("License 状态: %s (%s)", result.status, result.message)

    # ── M5: 缓存 License 验签结果 (供离线使用) ──
    from app.application.finance.offline_cache_service import OfflineCacheService
    cache_svc = OfflineCacheService(settings=settings)
    cache_svc.cache_verification(result)

    if result.payload:
        p = result.payload
        mf: dict = p.get("module_flags", {})
        with session_factory() as s:
            existing = s.query(Tenant).filter_by(id=p["merchant_id"]).first()
            if not existing:
                existing = Tenant(id=p["merchant_id"])
                s.add(existing)
            # 激活码锁定字段 – 每次启动从 License 重载确保一致
            existing.license_store_name = p.get("store_name", "未授权门店")
            existing.license_type = p.get("type", "single")
            existing.license_tier = p.get("tier", "single")
            existing.parent_tenant_id = p.get("parent_merchant_id") or None
            existing.max_stores = p.get("max_stores", 1)
            existing.hardware_fingerprint = p.get("hardware_fingerprint")
            # 经营信息 – 仅在首次创建时写默认值，后续保留用户本地修改
            if not existing.contact_name:
                existing.contact_name = p.get("contact", "")
            if not existing.phone:
                existing.phone = p.get("phone", "")
            if existing.license_expire_at is None and p.get("expire_at"):
                from datetime import datetime

                try:
                    existing.license_expire_at = datetime.fromisoformat(
                        p["expire_at"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass
            s.commit()

            # 挂到 app.state 供前端快速访问
            app.state.tenant = {
                "id": existing.id,
                "license_store_name": existing.license_store_name,
                "license_type": existing.license_type,
                "license_tier": existing.license_tier,
                "parent_tenant_id": existing.parent_tenant_id,
                "max_stores": existing.max_stores,
                "flags": mf,
            }
            log.info(
                f"租户同步完成: {existing.license_store_name} ({existing.license_type})"
            )

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

    elapsed = time.time() - getattr(app.state, "started_at", time.time())
    log.info(f"Cashier 已关闭 (运行 {elapsed:.1f}s)")

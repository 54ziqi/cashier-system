"""
测试共享 fixtures
- 临时 SQLite 数据库（每次测试后清理）
- 测试用 session_factory
- FastAPI TestClient
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

# 跳过云端的公钥校验 (cloud/data/license_pub.pem 不存在于测试环境)
os.environ.setdefault("CLOUD_SKIP_PUBKEY_CHECK", "1")

import pytest
from fastapi.testclient import TestClient

# 固定的测试管理员密码（避免模块 reload 导致密码不一致）
_TEST_ADMIN_PWD = "Test@Admin123"


@pytest.fixture(scope="function")
def test_home() -> Path:
    """每个测试函数独立的临时家目录"""
    d = Path(tempfile.mkdtemp(prefix="cashier_test_"))
    os.environ["CASHIER_HOME"] = str(d)
    return d


@pytest.fixture(scope="function")
def app(test_home):
    """每个测试函数创建全新的 FastAPI 应用实例"""
    # 重置模块状态
    from app.infra.db import engine as engine_mod

    # 完全重置引擎（强制重新创建，避免不同 test_home 间的 DB 复用）
    try:
        if engine_mod._engine is not None:
            engine_mod._engine.dispose()
    except Exception:
        pass
    engine_mod._engine = None
    engine_mod._SessionLocal = None

    from app.bootstrap import bootstrap
    from app.config import load_settings

    settings = load_settings("lite")
    # 强制使用测试 home 目录（Settings.home 默认值在类加载时已固定）
    settings.home = test_home
    settings._session_secret = b"test-secret-key-for-unit-tests-only-1234567890"
    bootstrap(settings)

    engine_mod.init_engine(settings)
    from app.infra.db.migrations import run_migrations

    run_migrations()

    from app import create_app

    app = create_app(settings)

    from app.application.member.member_service import MemberService
    from app.application.product.product_service import ProductService
    from app.kernel.auth.engine import OfflineAuthEngine
    from app.kernel.license.trial import generate_trial_license
    from app.kernel.license.verifier import LicenseVerifier

    app.state.auth = OfflineAuthEngine(
        session_factory=engine_mod.session_factory,
        secret=settings._session_secret,
        cfg=settings,
    )

    # 创建/重置初始管理员（使用固定密码）
    with engine_mod.session_factory() as s:
        from app.infra.db.models import LocalCredential

        existing = s.query(LocalCredential).filter_by(username="admin").first()
        if existing:
            s.delete(existing)
            s.commit()
    app.state.auth.create_user("admin", _TEST_ADMIN_PWD, "merchant_admin")
    app.state._test_admin_pwd = _TEST_ADMIN_PWD

    # 加载 License
    pub_pem = (settings.secrets_dir / "license_pub.pem").read_bytes()
    verifier = LicenseVerifier(pub_pem, grace_days=settings.license.grace_days)
    if not settings.license_path.exists() and settings.license.allow_trial:
        priv_pem = (settings.secrets_dir / "license_priv.pem").read_bytes()
        generate_trial_license(priv_pem, settings.license_path, days=30)
    app.state.license = verifier.verify(settings.license_path)

    # Seed demo data
    ProductService(merchant_id="local").seed_demo_products()
    MemberService(merchant_id="local").seed_demo_members()

    yield app

    # 清理
    try:
        engine_mod.get_engine().dispose()
    except Exception:
        pass
    engine_mod._engine = None
    engine_mod._SessionLocal = None


@pytest.fixture(scope="function")
def client(app) -> Generator:
    """FastAPI TestClient"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def auth_headers(client, app) -> dict:
    """通过 login 接口获取认证 headers"""
    pwd = getattr(app.state, "_test_admin_pwd", _TEST_ADMIN_PWD)
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": pwd}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def db_session(app) -> Generator:
    """提供独立的数据库 session"""
    from app.infra.db.engine import session_factory

    with session_factory() as s:
        yield s


@pytest.fixture(scope="function")
def auth_engine(app):
    """返回 OfflineAuthEngine 实例"""
    return app.state.auth


@pytest.fixture(scope="function")
def sample_products(app) -> list:
    """返回示例商品列表"""
    from app.infra.db.engine import session_factory
    from app.infra.db.models import Product

    with session_factory() as s:
        products = (
            s.query(Product).filter_by(merchant_id="local", status="active").all()
        )
        return [
            {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock}
            for p in products
        ]

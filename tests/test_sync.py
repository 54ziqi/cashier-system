"""
日结签名导出 + 云推送测试
"""

from __future__ import annotations

import json

import pytest

from app.infra.sync.cloud_push import enqueue
from app.infra.sync.daily_export import (
    build_daily_digest,
    export_signed_digest,
    sign_payload,
)


@pytest.fixture
def rsa_key(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    priv_pem = tmp_path / "priv.pem"
    pub_pem = tmp_path / "pub.pem"
    priv_pem.write_bytes(
        priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_pem.write_bytes(
        pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return priv_pem.read_bytes(), pub_pem.read_bytes()


class TestDailyDigest:
    def test_build_returns_structure(self, tmp_path):
        import os

        os.environ["CASHIER_HOME"] = str(tmp_path)
        from app.infra.db import engine as engine_mod

        engine_mod._engine = None
        engine_mod._SessionLocal = None
        from app.bootstrap import bootstrap
        from app.config import load_settings

        settings = load_settings("lite")
        settings.home = tmp_path
        bootstrap(settings)
        engine_mod.init_engine(settings)
        from app.infra.db.migrations import run_migrations

        run_migrations()
        d = build_daily_digest(day="2026-09-13")
        assert "merchant_id" in d
        assert "date" in d
        assert "gross_sales" in d
        assert "order_count" in d
        engine_mod._engine.dispose()
        engine_mod._engine = None
        engine_mod._SessionLocal = None


class TestSignature:
    def test_sign_and_verify(self, rsa_key):
        priv, pub = rsa_key
        payload = {"a": 1, "b": [1, 2, 3]}
        sig = sign_payload(payload, priv)
        # verify via auth module
        from cryptography.hazmat.primitives import serialization

        from cloud.auth import verify_digest

        key = serialization.load_pem_public_key(pub)
        assert verify_digest(payload, sig, pub_key=key) is True

    def test_tampered_payload_fails(self, rsa_key):
        priv, pub = rsa_key
        payload = {"a": 1}
        sig = sign_payload(payload, priv)
        from cryptography.hazmat.primitives import serialization

        from cloud.auth import verify_digest

        key = serialization.load_pem_public_key(pub)
        payload2 = {"a": 2}
        assert verify_digest(payload2, sig, pub_key=key) is False


class TestExport:
    def test_export_creates_file(self, rsa_key, tmp_path):
        import os

        os.environ["CASHIER_HOME"] = str(tmp_path)
        from app.infra.db import engine as engine_mod

        engine_mod._engine = None
        engine_mod._SessionLocal = None
        from app.bootstrap import bootstrap
        from app.config import load_settings

        settings = load_settings("lite")
        settings.home = tmp_path
        bootstrap(settings)
        engine_mod.init_engine(settings)
        from app.infra.db.migrations import run_migrations

        run_migrations()

        priv, _ = rsa_key
        out = tmp_path / "exports"
        day = "2026-09-13"
        fn = export_signed_digest(
            priv, out_dir=out, day=day, merchant_id="test", store_name="测试店"
        )
        assert fn.exists()
        record = json.loads(fn.read_text())
        assert "payload" in record
        assert "signature" in record
        engine_mod._engine.dispose()
        engine_mod._engine = None
        engine_mod._SessionLocal = None


class TestPushQueue:
    def test_enqueue_and_retry(self, tmp_path):
        src = tmp_path / "daily_2026-09-13.json"
        src.write_text(json.dumps({"payload": {"a": 1}, "signature": "x"}))
        from app.infra.sync import cloud_push as cp

        orig = cp.PUSH_QUEUE
        cp.PUSH_QUEUE = tmp_path / ".pending"
        try:
            enqueue(src)
            assert (cp.PUSH_QUEUE / src.name).exists()
            # retry with unreachable URL → remains in queue
            ok, fail = cp.retry_pending(cloud_url="http://127.0.0.1:1", max_retry=1)
            assert fail == 1
            assert (cp.PUSH_QUEUE / src.name).exists()
        finally:
            cp.PUSH_QUEUE = orig

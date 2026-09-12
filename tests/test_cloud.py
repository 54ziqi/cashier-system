"""
云端聚合服务测试 (独立进程, 独立 DB)

覆盖: ingest / dashboard / chain_summary / stores / tenants / auth / signature
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cloud.main import app
from cloud.models import Base, init_db
from cloud.auth import verify_digest


@pytest.fixture(scope="function")
def cloud_client(tmp_path):
    """每个测试使用独立的内存 SQLite"""
    db_path = str(tmp_path / "test_cloud.db")
    import cloud.main as cm
    cm.SessionLocal = init_db(db_path)
    with TestClient(app) as c:
        yield c


def _payload(mid="m_test", day="2026-09-13", rev=10000, cnt=5):
    return {
        "merchant_id": mid,
        "store_name": "测试店",
        "parent_merchant_id": "",
        "max_stores": 1,
        "date": day,
        "gross_sales": rev,
        "order_count": cnt,
    }


class TestCloudIngest:
    def test_ingest_ok(self, cloud_client):
        body = {"payload": _payload(), "sig": "demo"}
        r = cloud_client.post("/cloud/v1/ingest", json=body)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_ingest_registers_tenant(self, cloud_client):
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})
        r = cloud_client.get("/cloud/v1/tenants", headers={"Authorization": "Bearer demo-admin"})
        data = r.json()
        assert len(data) == 1
        assert data[0]["store_name"] == "测试店"

    def test_chain_parent_ingest_with_children(self, cloud_client):
        base = _payload()
        parent  = {**base, "merchant_id": "m_parent",  "store_name": "母店"}
        child1  = {**base, "merchant_id": "m_child1",  "store_name": "子店A", "parent_merchant_id": "m_parent"}
        child2  = {**base, "merchant_id": "m_child2",  "store_name": "子店B", "parent_merchant_id": "m_parent"}

        for p in [parent, child1, child2]:
            r = cloud_client.post("/cloud/v1/ingest", json={"payload": p, "sig": "x"})
            assert r.status_code == 200


class TestCloudAPI:
    def test_single_dashboard(self, cloud_client):
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})
        r = cloud_client.get(
            "/cloud/v1/dashboard/m_test?days=7",
            headers={"Authorization": "Bearer demo-admin"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["merchant_id"] == "m_test"
        assert "series" in data

    def test_chain_summary(self, cloud_client):
        base = _payload()
        parent = {**base, "merchant_id": "m_parent", "store_name": "母店"}
        child1 = {**base, "merchant_id": "m_child1", "store_name": "子店A", "parent_merchant_id": "m_parent"}
        child2 = {**base, "merchant_id": "m_child2", "store_name": "子店B", "parent_merchant_id": "m_parent"}
        for p in [parent, child1, child2]:
            cloud_client.post("/cloud/v1/ingest", json={"payload": p, "sig": "x"})
        r = cloud_client.get(
            "/cloud/v1/chain/m_parent/summary?days=7",
            headers={"Authorization": "Bearer demo-admin"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_revenue"] >= 0
        assert "ranking" in data

    def test_chain_stores(self, cloud_client):
        base = _payload()
        cloud_client.post("/cloud/v1/ingest", json={"payload": {**base, "merchant_id": "m_parent"}, "sig": "x"})
        cloud_client.post("/cloud/v1/ingest", json={"payload": {**base, "merchant_id": "m_child1", "parent_merchant_id": "m_parent"}, "sig": "x"})
        r = cloud_client.get(
            "/cloud/v1/chain/m_parent/stores",
            headers={"Authorization": "Bearer demo-admin"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["parent_id"] == "m_parent"
        assert data["local_only"] is False


class TestCloudRBAC:
    def test_no_auth_returns_401(self, cloud_client):
        r = cloud_client.get("/cloud/v1/tenants")
        assert r.status_code == 401

    def test_invalid_token_returns_403_or_401(self, cloud_client):
        # 首个 tenant 未注册前, 任何 token 都视为未激活
        r = cloud_client.get("/cloud/v1/tenants", headers={"Authorization": "Bearer anything"})
        assert r.status_code in (401, 403)

    def test_chain_summary_blocks_unregistered(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/chain/m_nonexist/summary",
            headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code in (401, 403)


class TestSignature:
    def test_verify_no_key_trusts(self):
        """演示模式: 无公钥时 trust"""
        ok = verify_digest({"a": 1}, "any-sig")
        assert ok is True

    def test_verify_bad_signature_rejected(self, tmp_path):
        """有公钥时，错签拒绝"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = priv.public_key()
        pem = tmp_path / "pub.pem"
        pem.write_bytes(pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        from cloud.auth import _load_public_key
        key = _load_public_key(pem)
        assert key is not None
        ok = verify_digest({"a": 1}, "invalid-sig", pub_key=key)
        assert ok is False

"""
云端聚合服务测试 (独立进程, 独立 DB)

覆盖: ingest / dashboard / chain_summary / stores / tenants / auth / signature / 安全修复 (P0-P1)
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cloud.auth import ensure_pubkey_on_startup, verify_digest
from cloud.main import app
from cloud.models import init_db


@pytest.fixture(scope="function")
def cloud_client(tmp_path):
    """每个测试使用独立的内存 SQLite"""
    db_path = str(tmp_path / "test_cloud.db")
    import cloud.main as cm

    cm.SessionLocal = init_db(db_path)
    with TestClient(app) as c:
        yield c


def _payload(
    mid="m_test", day="2026-09-13", rev=10000, cnt=5, parent="", store="测试店"
):
    return {
        "merchant_id": mid,
        "store_name": store,
        "parent_merchant_id": parent,
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
        # 首次 ingest 后自动注册为管理员
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})
        # 用首次 ingest 的 merchant_id 作为 Bearer token
        r = cloud_client.get(
            "/cloud/v1/tenants",
            headers={"Authorization": "Bearer m_test"},
        )
        assert r.status_code == 200, r.json()
        data = r.json()
        assert len(data) == 1
        assert data[0]["store_name"] == "测试店"

    def test_chain_parent_ingest_with_children(self, cloud_client):
        base = _payload()
        parent = {**base, "merchant_id": "m_parent", "store_name": "母店"}
        child1 = {
            **base,
            "merchant_id": "m_child1",
            "store_name": "子店A",
            "parent_merchant_id": "m_parent",
        }
        child2 = {
            **base,
            "merchant_id": "m_child2",
            "store_name": "子店B",
            "parent_merchant_id": "m_parent",
        }

        for p in [parent, child1, child2]:
            r = cloud_client.post("/cloud/v1/ingest", json={"payload": p, "sig": "x"})
            assert r.status_code == 200


class TestCloudAPI:
    @pytest.fixture(autouse=True)
    def _seed(self, cloud_client):
        """预置测试数据"""
        base = _payload()
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {**base, "merchant_id": "m_parent", "store_name": "母店"},
                "sig": "x",
            },
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {
                    **base,
                    "merchant_id": "m_child1",
                    "store_name": "子店A",
                    "parent_merchant_id": "m_parent",
                },
                "sig": "x",
            },
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {
                    **base,
                    "merchant_id": "m_child2",
                    "store_name": "子店B",
                    "parent_merchant_id": "m_parent",
                },
                "sig": "x",
            },
        )

    def test_single_dashboard(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/dashboard/m_parent?days=7",
            headers={"Authorization": "Bearer m_parent"},
        )
        assert r.status_code == 200, r.json()
        data = r.json()
        assert data["merchant_id"] == "m_parent"
        assert "series" in data

    def test_chain_summary(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/chain/m_parent/summary?days=7",
            headers={"Authorization": "Bearer m_parent"},
        )
        assert r.status_code == 200, r.json()
        data = r.json()
        assert data["total_revenue"] >= 0
        assert "ranking" in data

    def test_chain_stores(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/chain/m_parent/stores",
            headers={"Authorization": "Bearer m_parent"},
        )
        assert r.status_code == 200, r.json()
        data = r.json()
        assert data["parent_id"] == "m_parent"
        assert data["local_only"] is False


class TestCloudRBAC:
    def test_no_auth_returns_401(self, cloud_client):
        r = cloud_client.get("/cloud/v1/tenants")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, cloud_client):
        # 先注册 m_test 作为租户
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})
        # 再用不存在的 token 访问
        r = cloud_client.get(
            "/cloud/v1/tenants",
            headers={"Authorization": "Bearer non-existent-token"},
        )
        assert r.status_code == 401

    def test_chain_summary_blocks_unregistered(self, cloud_client):
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})
        r = cloud_client.get(
            "/cloud/v1/chain/m_nonexist/summary",
            headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code == 401

    def test_chain_summary_blocks_child_token_for_sibling(self, cloud_client):
        """子店 token 不能访问其他母店的 chain (P0-C2 ownership 校验)"""
        base = _payload()
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {**base, "merchant_id": "m_parent1", "store_name": "母店1"},
                "sig": "x",
            },
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {
                    **base,
                    "merchant_id": "m_child_of_parent1",
                    "store_name": "子店A",
                    "parent_merchant_id": "m_parent1",
                },
                "sig": "x",
            },
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": {**base, "merchant_id": "m_parent2", "store_name": "母店2"},
                "sig": "x",
            },
        )
        # 母店2 的 summary 不应该被 m_child_of_parent1 访问
        r = cloud_client.get(
            "/cloud/v1/chain/m_parent2/summary",
            headers={"Authorization": "Bearer m_child_of_parent1"},
        )
        assert r.status_code == 403


class TestSignature:
    def test_verify_no_key_trusts(self):
        """演示模式: 无公钥时 trust"""
        ok = verify_digest({"a": 1}, "any-sig")
        assert ok is True

    def test_verify_bad_signature_rejected(self, tmp_path):
        """有公钥时，错签拒绝"""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = priv.public_key()
        pem = tmp_path / "pub.pem"
        pem.write_bytes(
            pub.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        from cloud.auth import _load_public_key

        key = _load_public_key(pem)
        assert key is not None
        ok = verify_digest({"a": 1}, "invalid-sig", pub_key=key)
        assert ok is False


# ── P0-C1: 启动时必须校验公钥文件 ──────────────────────────────────────


class TestPubkeyStartup:
    def test_ensure_pubkey_raises_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLOUD_SKIP_PUBKEY_CHECK", raising=False)
        missing = tmp_path / "not_exist.pem"
        with pytest.raises(SystemExit, match="Missing"):
            ensure_pubkey_on_startup(missing)

    def test_ensure_pubkey_ok_when_exists(self, tmp_path, monkeypatch):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        monkeypatch.delenv("CLOUD_SKIP_PUBKEY_CHECK", raising=False)
        pem = tmp_path / "license_pub.pem"
        priv = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        ).public_key()
        pem.write_bytes(
            priv.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        ensure_pubkey_on_startup(pem)  # 不抛异常

    def test_ensure_pubkey_skipped_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLOUD_SKIP_PUBKEY_CHECK", "1")
        ensure_pubkey_on_startup(tmp_path / "nope.pem")  # 不抛异常


# ── P0-C3: WebSocket 鉴权 ──────────────────────────────────────────────


class TestWebSocketAuth:
    def test_websocket_accepts_valid_token(self, cloud_client):
        """WS 握手传入有效 token → 连接建立"""
        cloud_client.post("/cloud/v1/ingest", json={"payload": _payload(), "sig": "x"})

        with cloud_client.websocket_connect("/cloud/ws/m_test") as ws:
            ws.send_text(json.dumps({"token": "m_test"}))
            ws.send_text("ping")
            resp = ws.receive_text()
            assert resp == "pong"

    def test_websocket_rejects_without_valid_token(self, cloud_client):
        """WS 握手传入无效 token → close(code=4001)"""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as exc:
            with cloud_client.websocket_connect("/cloud/ws/m_test") as ws:
                ws.send_text(json.dumps({"token": "bad-token"}))
                ws.send_text("ping")
                ws.receive_text()
        # 握手失败后 server 用 4001 关闭
        assert exc.value.code == 4001

    def test_websocket_rejects_non_json(self, cloud_client):
        """WS 握手传入非 JSON → close(4001)"""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as exc:
            with cloud_client.websocket_connect("/cloud/ws/m_test") as ws:
                ws.send_text("not-json-at-all")
                ws.send_text("ping")
                ws.receive_text()
        assert exc.value.code == 4001

    def test_websocket_rejects_missing_token(self, cloud_client):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as exc:
            with cloud_client.websocket_connect("/cloud/ws/m_test") as ws:
                ws.send_text(json.dumps({"foo": "bar"}))
                ws.send_text("ping")
                ws.receive_text()
        assert exc.value.code == 4001


# ── P0-C4: CORS 白名单 ─────────────────────────────────────────────────


class TestCORS:
    def test_cors_blocks_foreign_origin(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/tenants",
            headers={"Origin": "https://evil.example.com"},
        )
        assert r.status_code == 400

    def test_cors_allows_whitelisted_origin(self, cloud_client):
        r = cloud_client.get(
            "/cloud/v1/dashboard/m_test?days=7",
            headers={
                "Origin": "http://localhost:9000",
                "Authorization": "Bearer m_test",
            },
        )
        # 401 OK as this dashboard doesn't exist; but CORS must not block
        assert r.status_code != 400

    def test_same_origin_no_header_passes(self, cloud_client):
        """无 Origin 头时 (同源), 应放行"""
        r = cloud_client.get("/cloud/v1/tenants")
        assert r.status_code != 400


# ── P0-C5: 幂等同日期 ingest ──────────────────────────────────────────


class TestIdempotentIngest:
    def test_ingest_idempotent_on_same_date(self, cloud_client):
        """同一 (merchant_id, date) 重复 ingest 应覆盖而非报错"""
        cloud_client.post(
            "/cloud/v1/ingest", json={"payload": _payload(rev=10000, cnt=5), "sig": "x"}
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={"payload": _payload(rev=25000, cnt=10), "sig": "x"},
        )
        # dash 板应返回覆盖后的值
        r = cloud_client.get(
            "/cloud/v1/dashboard/m_test?days=7",
            headers={"Authorization": "Bearer m_test"},
        )
        assert r.status_code == 200
        data = r.json()
        total = sum(s["revenue"] for s in data["series"])
        assert total == 25000  # 第二次覆盖第一次


# ── P2-S3 补充负向测试 ────────────────────────────────────────────────


class TestNegativeIngress:
    def test_ingest_bad_signature_rejected(self, cloud_client, tmp_path, monkeypatch):
        """C-1: 若公钥存在则错签被拒"""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        pem = tmp_path / "license_pub.pem"
        priv = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        ).public_key()
        pem.write_bytes(
            priv.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        # 使用 monkeypatch 临时切换公钥路径（测试结束后自动恢复）
        monkeypatch.setenv("CLOUD_PUBKEY_PATH", str(pem))
        r = cloud_client.post(
            "/cloud/v1/ingest", json={"payload": _payload(), "sig": "invalid-sig-b64"}
        )
        # 签名校验失败应返回 400
        assert r.status_code == 400, r.json()

    def test_ingest_missing_payload_rejected(self, cloud_client):
        r = cloud_client.post("/cloud/v1/ingest", json={"sig": "x"})
        assert r.status_code == 400

    def test_ingest_tenant_isolation(self, cloud_client):
        """W-5 / C-2: 匿名 tenant 不可见其他 tenant 的数据"""
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": _payload(mid="m_tenant_a", store="A店", rev=99999),
                "sig": "x",
            },
        )
        cloud_client.post(
            "/cloud/v1/ingest",
            json={
                "payload": _payload(mid="m_tenant_b", store="B店", rev=11111),
                "sig": "x",
            },
        )
        # m_tenant_b 拿不到 A 店的 dash (A 是 B 的平级, 非 parent/child)
        r = cloud_client.get(
            "/cloud/v1/dashboard/m_tenant_a?days=7",
            headers={"Authorization": "Bearer m_tenant_b"},
        )
        # 403 表示 token 有效但无权（母店读子店 / 自己读自己 才放行）
        assert r.status_code == 403

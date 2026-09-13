"""M1 测试：订单全生命周期按业态差异化 + 桌台管理"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.infra.db.models import DiningTable, OrderStatusLog, ProductSpecGroup, ProductSpecOption


# ── 订单状态机 (按业态) ──────────────────────────────────────────


class TestOrderStatusLifecycle:
    """验证订单状态流转是否满足各业态差异化需求"""

    def test_fast_food_flow(self, client, auth_headers, sample_products):
        """快餐：pending → paid → making → ready → served"""
        pid = sample_products[0]["id"]
        # checkout (pending → paid + completed via domain)
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        assert r.status_code == 200
        oid = r.json()["order_id"]

        # 推进到 making
        r = client.post(f"/api/v1/merchant/orders/{oid}/status",
                        json={"transition": "making"}, headers=auth_headers)
        assert r.status_code == 200, r.text

        # 推进到 ready
        r = client.post(f"/api/v1/merchant/orders/{oid}/status",
                        json={"transition": "ready", "queue_no": "A01"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["queue_no"] == "A01"

        # 推进到 served
        r = client.post(f"/api/v1/merchant/orders/{oid}/status",
                        json={"transition": "served"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["kitchen_status"] == "served"

    def test_bakery_immediate_complete(self, client, auth_headers, sample_products):
        """烘焙/零售：paid → completed 直接完成"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]

        # completed
        r = client.post(f"/api/v1/merchant/orders/{oid}/status",
                        json={"transition": "completed"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_void_requires_admin(self, client, auth_headers, sample_products):
        """整单作废：admin 可作废流转中订单；completed 不可作废"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]

        # 推进到 making 状态
        client.post(f"/api/v1/merchant/orders/{oid}/status",
                    json={"transition": "making"}, headers=auth_headers)

        # admin 可以作废流转中订单
        r = client.post(f"/api/v1/merchant/orders/{oid}/void",
                        json={"reason": "顾客退款"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "voided"

    def test_void_completed_rejected(self, client, auth_headers, sample_products):
        """已完成的订单不允许作废（应走退款流程）"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]
        # completed 状态不可作废
        r = client.post(f"/api/v1/merchant/orders/{oid}/void",
                        json={"reason": "顾客退款"}, headers=auth_headers)
        assert r.status_code == 400, r.text

    def test_void_idempotent_rejected(self, client, auth_headers, sample_products):
        """已作废的订单不可重复作废"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]
        client.post(f"/api/v1/merchant/orders/{oid}/status",
                    json={"transition": "making"}, headers=auth_headers)
        # 第一次作废
        client.post(f"/api/v1/merchant/orders/{oid}/void",
                    json={"reason": "test"}, headers=auth_headers)
        # 第二次应失败
        r = client.post(f"/api/v1/merchant/orders/{oid}/void",
                        json={"reason": "again"}, headers=auth_headers)
        assert r.status_code == 400, r.text

    def test_status_log_written(self, client, auth_headers, sample_products, app):
        """状态变更必须写入 order_status_logs"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]

        r = client.post(f"/api/v1/merchant/orders/{oid}/status",
                        json={"transition": "making"}, headers=auth_headers)
        assert r.status_code == 200

        from app.infra.db.engine import session_factory
        with session_factory() as s:
            logs = s.query(OrderStatusLog).filter_by(order_id=oid).all()
            assert len(logs) >= 1
            assert logs[0].to_status == "making"

    def test_urge_order(self, client, auth_headers, sample_products):
        """催菜：仅 making 状态可催"""
        pid = sample_products[0]["id"]
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}], "pay_method": "cash", "cash_amount": 99999},
            headers=auth_headers,
        )
        oid = r.json()["order_id"]

        # 先推进到 making
        client.post(f"/api/v1/merchant/orders/{oid}/status",
                    json={"transition": "making"}, headers=auth_headers)
        # 催菜
        r = client.post(f"/api/v1/merchant/orders/{oid}/urge", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["urged"] is True


# ── 桌台管理 ──────────────────────────────────────────────────────


class TestTableManagement:
    """验证桌台 CRUD + 状态流转"""

    def test_create_table(self, client, auth_headers):
        r = client.post(
            "/api/v1/merchant/tables",
            json={"name": "A01", "capacity": 4, "pos_x": 100, "pos_y": 200},
            headers=auth_headers,
        )
        assert r.status_code in (200, 201), r.text
        assert r.json()["name"] == "A01"

    def test_list_tables(self, client, auth_headers):
        client.post(
            "/api/v1/merchant/tables",
            json={"name": "B01", "capacity": 2},
            headers=auth_headers,
        )
        r = client.get("/api/v1/merchant/tables", headers=auth_headers)
        assert r.status_code == 200
        names = [t["name"] for t in r.json()["items"]]
        assert "B01" in names

    def test_seat_clear_cycle(self, client, auth_headers):
        """空桌 → 开台 → 清台"""
        r = client.post(
            "/api/v1/merchant/tables",
            json={"name": "T01", "capacity": 4},
            headers=auth_headers,
        )
        tid = r.json()["id"]

        # seat
        r = client.post(f"/api/v1/merchant/tables/{tid}/seat", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "seated"

        # clear
        r = client.post(f"/api/v1/merchant/tables/{tid}/clear", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "empty"

    def test_occupy_and_vacate(self, client, auth_headers, sample_products):
        """开台 → 绑定订单 → 解绑"""
        pid = sample_products[0]["id"]

        # create a table
        tr = client.post(
            "/api/v1/merchant/tables",
            json={"name": "OCC1", "capacity": 4},
            headers=auth_headers,
        )
        tid = tr.json()["id"]
        client.post(f"/api/v1/merchant/tables/{tid}/seat", headers=auth_headers)

        # checkout with table_id
        r = client.post(
            "/api/v1/merchant/cashier/checkout",
            json={"items": [{"product_id": pid, "quantity": 1}],
                  "pay_method": "cash", "cash_amount": 99999,
                  "table_id": tid, "table_name": "OCC1"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        oid = r.json()["order_id"]

        # order 详情里能看到 table_id
        r = client.get(f"/api/v1/merchant/orders/{oid}", headers=auth_headers)
        assert r.json().get("table_id") == tid


# ── 商品规格 (Specs) ─────────────────────────────────────────────


class TestProductSpecs:
    """验证商品规格组/选项 CRUD"""

    def test_set_and_get_specs(self, client, auth_headers, sample_products):
        pid = sample_products[0]["id"]
        groups = [{"group_name": "杯型", "required": True, "min_select": 1, "max_select": 1}]
        options = [
            {"group_name": "杯型", "value": "中杯", "price_delta": 0},
            {"group_name": "杯型", "value": "大杯", "price_delta": 200},
        ]
        r = client.post(
            f"/api/v1/merchant/products/{pid}/specs",
            json={"groups": groups, "options": options},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        r = client.get(f"/api/v1/merchant/products/{pid}/specs", headers=auth_headers)
        assert len(r.json()["groups"]) >= 1
        assert any(opt["value"] == "大杯" and opt["price_delta"] == 200
                   for opt in r.json()["options"])

    def test_86_marking(self, client, auth_headers, sample_products):
        pid = sample_products[0]["id"]
        r = client.post(
            f"/api/v1/merchant/products/{pid}/86",
            json={"is_86": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_86"] == 1

        r = client.get(f"/api/v1/merchant/products/86/list", headers=auth_headers)
        assert pid in r.json()["skus"]

    def test_bom_setting(self, client, auth_headers, sample_products):
        pid = sample_products[0]["id"]
        bom = [{"material_id": "mat_001", "qty": 0.2, "unit": "kg"}]
        r = client.post(
            f"/api/v1/merchant/products/{pid}/bom",
            json={"bom": bom},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["id"] == pid

    def test_combo_toggle(self, client, auth_headers, sample_products):
        pid = sample_products[0]["id"]
        r = client.post(
            f"/api/v1/merchant/products/{pid}/combo",
            json={"is_combo": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_combo"] == 1

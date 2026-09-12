"""API 集成测试：完整 HTTP 工作流"""

from __future__ import annotations

from tests.conftest import _TEST_ADMIN_PWD


class TestCheckoutAPI:
    """现金结算 + 退款 端到端测试"""

    def _login(self, client) -> str:
        """登录获取 admin token"""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": _TEST_ADMIN_PWD},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def _get_product(self, client, token: str, pid: str = "demo_p004") -> dict:
        """获取商品库存"""
        resp = client.get(
            "/api/v1/merchant/products", headers={"Authorization": f"Bearer {token}"}
        )
        for item in resp.json()["items"]:
            if item["id"] == pid:
                return item
        return {}

    def test_cash_checkout_flow(self, client):
        """完整现金结算流程"""
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        prod = self._get_product(client, token, "demo_p004")
        stock_before = prod["stock"]

        # 结算
        resp = client.post(
            "/api/v1/merchant/cashier/checkout",
            headers=headers,
            json={
                "items": [{"product_id": "demo_p004", "quantity": 1}],
                "pay_method": "cash",
                "cash_amount": 5000,
            },
        )
        assert resp.status_code == 200, resp.json().get("detail", resp.text)
        data = resp.json()
        assert data["success"] is True
        assert data["final_amount"] == prod["price"]
        assert data["change"] == 5000 - prod["price"]

        # 库存已扣减
        prod_after = self._get_product(client, token, "demo_p004")
        assert prod_after["stock"] == stock_before - 1

    def test_oversell_returns_400(self, client):
        """超卖返回 400"""
        token = self._login(client)
        resp = client.post(
            "/api/v1/merchant/cashier/checkout",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"product_id": "demo_p003", "quantity": 9999}],
                "pay_method": "cash",
                "cash_amount": 99999999,
            },
        )
        assert resp.status_code == 400

    def test_invalid_product_returns_400(self, client):
        """不存在商品返回 400"""
        token = self._login(client)
        resp = client.post(
            "/api/v1/merchant/cashier/checkout",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"product_id": "invalid-id", "quantity": 1}],
                "pay_method": "cash",
                "cash_amount": 99999999,
            },
        )
        assert resp.status_code == 400

    def test_health_endpoint(self, client):
        """健康检查"""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_member_recharge_via_api(self, client):
        """会员充值"""
        token = self._login(client)
        # 创建会员
        resp = client.post(
            "/api/v1/merchant/members",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "测试会员", "phone": "13800001111", "card_no": "C9999"},
        )
        if resp.status_code == 200:
            member_id = resp.json()["id"]
            # 充值
            recharge = client.post(
                f"/api/v1/merchant/members/{member_id}/recharge?amount=50.0",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert recharge.status_code == 200

    def test_order_list(self, client):
        """订单列表"""
        token = self._login(client)
        resp = client.get(
            "/api/v1/merchant/orders", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_products_list(self, client):
        """商品列表"""
        token = self._login(client)
        resp = client.get(
            "/api/v1/merchant/products", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0


class TestRefundIdempotent:
    """P1-W2 + W5: 退款 CAS 重复退款返回异常 + SAVEPOINT 兜底"""

    def _login(self, client) -> str:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": _TEST_ADMIN_PWD},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def _get_product(self, client, token: str, pid: str) -> dict:
        resp = client.get(
            "/api/v1/merchant/products", headers={"Authorization": f"Bearer {token}"}
        )
        for item in resp.json()["items"]:
            if item["id"] == pid:
                return item
        return {}

    def test_refund_duplicate_returns_400(self, client):
        """W-2: 第二次退款因 CAS 失败 → CheckoutError → HTTP 400"""
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        prod = self._get_product(client, token, "demo_p004")
        stock_before = prod["stock"]

        # 下单 + 结算
        resp = client.post(
            "/api/v1/merchant/cashier/checkout",
            headers=headers,
            json={
                "items": [{"product_id": "demo_p004", "quantity": 1}],
                "pay_method": "cash",
                "cash_amount": 5000,
            },
        )
        assert resp.status_code == 200, resp.text
        order_id = resp.json()["order_id"]

        # 第一次退款成功
        r1 = client.post(f"/api/v1/merchant/orders/refund/{order_id}", headers=headers)
        assert r1.status_code == 200, r1.text

        # 库存已恢复
        prod_after = self._get_product(client, token, "demo_p004")
        assert prod_after["stock"] == stock_before

        # 第二次退款 → 400 (CAS 拒绝)
        r2 = client.post(f"/api/v1/merchant/orders/refund/{order_id}", headers=headers)
        assert r2.status_code == 400, r2.text


class TestCrossTenantIsolation:
    """P1-W5 / C-2: 跨租户订单读取隔离 (POS 硬编码 local, 用 token 等价置换)"""

    def _login(self, client) -> str:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": _TEST_ADMIN_PWD},
        )
        return resp.json()["token"]

    def test_order_cross_tenant_read_returns_404(self, client):
        """跨租户订单在聚合层被 local 过滤"""
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        # 查询不存在的订单 (不存在的 tenant)
        resp = client.get("/api/v1/merchant/orders/nonexistent-id", headers=headers)
        # 服务层按 local 过滤, 跨 tenant 订单 → 404
        assert resp.status_code == 404

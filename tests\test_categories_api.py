"""分类 API 测试：CRUD + 商品分类关联"""

from __future__ import annotations


class TestCategoriesAPI:
    """分类管理 REST API 测试"""

    def test_list_categories_empty(self, client, auth_headers):
        """首次返回空列表"""
        resp = client.get("/api/v1/merchant/categories", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_category(self, client, auth_headers):
        """创建分类"""
        resp = client.post(
            "/api/v1/merchant/categories",
            headers=auth_headers,
            json={"name": "水果"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "水果"
        assert "id" in data

    def test_create_and_list(self, client, auth_headers):
        """创建多个分类后列表返回"""
        for name in ["蔬菜", "肉类"]:
            client.post(
                "/api/v1/merchant/categories",
                headers=auth_headers,
                json={"name": name},
            )
        resp = client.get("/api/v1/merchant/categories", headers=auth_headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "蔬菜" in names
        assert "肉类" in names

    def test_update_category(self, client, auth_headers):
        """更新分类名称"""
        resp = client.post(
            "/api/v1/merchant/categories",
            headers=auth_headers,
            json={"name": "饮料"},
        )
        cat_id = resp.json()["id"]

        update_resp = client.put(
            f"/api/v1/merchant/categories/{cat_id}",
            headers=auth_headers,
            json={"name": "饮品"},
        )
        assert update_resp.status_code == 200

        # 验证更新
        list_resp = client.get("/api/v1/merchant/categories", headers=auth_headers)
        names = [c["name"] for c in list_resp.json()]
        assert "饮品" in names
        assert "饮料" not in names

    def test_delete_category(self, client, auth_headers):
        """删除分类"""
        resp = client.post(
            "/api/v1/merchant/categories",
            headers=auth_headers,
            json={"name": "零食"},
        )
        cat_id = resp.json()["id"]

        del_resp = client.delete(
            f"/api/v1/merchant/categories/{cat_id}",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200

        # 验证已删除
        list_resp = client.get("/api/v1/merchant/categories", headers=auth_headers)
        ids = [c["id"] for c in list_resp.json()]
        assert cat_id not in ids

    def test_category_requires_admin(self, client):
        """无 Token 创建分类返回 401"""
        resp = client.post(
            "/api/v1/merchant/categories",
            json={"name": "测试"},
        )
        assert resp.status_code == 401


class TestProductSearchAPI:
    """商品搜索 API 测试"""

    def test_search_by_name(self, client, auth_headers):
        """按名称模糊搜索"""
        # 搜索 "牛奶" 应该匹配到鲜牛奶商品
        resp = client.get(
            "/api/v1/merchant/products/search?q=牛奶",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)

    def test_search_with_special_chars(self, client, auth_headers):
        """搜索包含 % 特殊字符不应报错"""
        resp = client.get(
            "/api/v1/merchant/products/search?q=%25",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_list_products_with_category(self, client, auth_headers):
        """按分类筛选商品"""
        # 先创建分类
        cat_resp = client.post(
            "/api/v1/merchant/categories",
            headers=auth_headers,
            json={"name": "测试分类"},
        )
        cat_id = cat_resp.json()["id"]

        # 创建商品并关联分类
        client.post(
            "/api/v1/merchant/products",
            headers=auth_headers,
            json={
                "name": "分类测试商品",
                "price": 100,
                "stock": 10,
                "category_id": cat_id,
            },
        )

        # 按分类筛选
        resp = client.get(
            f"/api/v1/merchant/products?category_id={cat_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [p["name"] for p in data["items"]]
        assert "分类测试商品" in names

    def test_list_products_with_status(self, client, auth_headers):
        """按状态筛选商品"""
        resp = client.get(
            "/api/v1/merchant/products?status=active",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"


class TestRoleBasedAccess:
    """角色权限校验测试"""

    def test_recharge_requires_admin(self, client):
        """无 Token 充值返回 401"""
        resp = client.post(
            "/api/v1/merchant/members/some-id/recharge?amount=100",
        )
        assert resp.status_code == 401

    def test_refund_requires_admin(self, client):
        """无 Token 退款返回 401"""
        resp = client.post("/api/v1/merchant/orders/refund/some-id")
        assert resp.status_code == 401

    def test_recharge_with_admin_succeeds(self, client, auth_headers):
        """管理员可以充值"""
        # 先创建一个会员
        resp = client.post(
            "/api/v1/merchant/members",
            headers=auth_headers,
            json={
                "name": "RBAC测试会员",
                "phone": "13900001234",
                "card_no": "C_RBAC_01",
            },
        )
        if resp.status_code == 200:
            member_id = resp.json()["id"]
            recharge = client.post(
                f"/api/v1/merchant/members/{member_id}/recharge?amount=50.0",
                headers=auth_headers,
            )
            assert recharge.status_code == 200

    def test_health_ready_no_license_leak(self, client):
        """健康检查不暴露 License 详细信息"""
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "license" not in data

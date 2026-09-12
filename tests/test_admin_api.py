"""Admin API 认证测试：无 Token / 无效 Token / 有效管理员 Token"""

from __future__ import annotations


class TestAdminAPIAuth:
    """管理员端点认证校验"""

    def test_no_token_returns_401(self, client):
        """不带 Token 访问 Admin API 返回 401"""
        resp = client.get("/api/v1/admin/merchants")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """无效 Token 返回 401"""
        resp = client.get(
            "/api/v1/admin/merchants",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    def test_invalid_format_token_returns_401(self, client):
        """格式错误的 Token 返回 401"""
        resp = client.get(
            "/api/v1/admin/licenses",
            headers={"Authorization": "Bearer not-a-valid-format"},
        )
        assert resp.status_code == 401

    def test_admin_can_list_merchants(self, client, auth_headers):
        """管理员可访问商户列表"""
        resp = client.get("/api/v1/admin/merchants", headers=auth_headers)
        assert resp.status_code == 200

    def test_admin_can_list_licenses(self, client, auth_headers):
        """管理员可访问授权列表"""
        resp = client.get("/api/v1/admin/licenses", headers=auth_headers)
        assert resp.status_code == 200

    def test_admin_can_create_merchant(self, client, auth_headers):
        """管理员可创建商户"""
        resp = client.post(
            "/api/v1/admin/merchants",
            headers=auth_headers,
            json={"name": "测试商户", "contact_name": "张三", "phone": "13800138000"},
        )
        assert resp.status_code == 200

    def test_revoked_token_rejected_for_admin(self, client, auth_headers):
        """撤销后的 Token 不可访问管理员端点"""
        token = auth_headers["Authorization"][7:]  # strip "Bearer "
        # 登出撤销 Token
        client.post("/api/v1/auth/logout", headers=auth_headers)
        # 再次访问应失败
        resp = client.get("/api/v1/admin/merchants", headers=auth_headers)
        assert resp.status_code == 401

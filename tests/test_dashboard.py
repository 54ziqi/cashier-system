"""
Dashboard 看板 API 测试

覆盖:
- 鉴权守卫（未登录 401、无效 token 401）
- 7 个 API 端点返回 200 + 响应结构校验
- /dashboard/tenant 返回店名与 license_type
- /dashboard/chain/stores 的 RBAC：single 版 403、chain_parent 版 200（本地 stub）
- License 升级回归：trial payload 新增字段（store_name / tier / max_stores / price_tier / module_flags.cloud_sync / module_flags.chain_view）
"""

from __future__ import annotations

import pytest


class TestDashboardAuth:
    """看板鉴权守卫"""

    def test_overview_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/overview")
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        resp = client.get(
            "/api/v1/dashboard/overview",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


class TestDashboardAPI:
    """看板 API 200 + 响应结构校验"""

    @pytest.fixture(autouse=True)
    def init(self, app):
        pass

    def _h(self, client, auth_headers):
        return auth_headers

    def test_tenant_info(self, client, auth_headers):
        """tenant 接口返回店名与 license_type"""
        resp = client.get(
            "/api/v1/dashboard/tenant", headers=self._h(client, auth_headers)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "store_name" in data
        assert data["license_type"] == "single"  # trial 默认 single
        assert "features" in data
        assert data["features"]["dashboard"] is True
        # single 版无 chain_view 也无 cloud_sync
        assert data["features"]["chain_view"] is False
        assert data["features"]["cloud_sync"] is False

    def test_overview_structure(self, client, auth_headers):
        resp = client.get(
            "/api/v1/dashboard/overview", headers=self._h(client, auth_headers)
        )
        assert resp.status_code == 200
        data = resp.json()
        for k in (
            "today_revenue",
            "today_count",
            "avg_ticket",
            "yesterday_revenue",
            "yoy_percent",
            "daily_7",
        ):
            assert k in data, f"missing {k}"
        assert isinstance(data["daily_7"], list)
        assert len(data["daily_7"]) == 7

    def test_trend(self, client, auth_headers):
        for r in ("7d", "30d", "90d"):
            resp = client.get(
                f"/api/v1/dashboard/trend?range={r}",
                headers=self._h(client, auth_headers),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["range"] == r
            assert "series" in data

    def test_category(self, client, auth_headers):
        resp = client.get(
            "/api/v1/dashboard/category?days=30",
            headers=self._h(client, auth_headers),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "top15" in data
        assert isinstance(data["top15"], list)

    def test_hourly(self, client, auth_headers):
        resp = client.get(
            "/api/v1/dashboard/hourly?days=7",
            headers=self._h(client, auth_headers),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hourly"]) == 24

    def test_cashier(self, client, auth_headers):
        resp = client.get(
            "/api/v1/dashboard/cashier?days=30",
            headers=self._h(client, auth_headers),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cashiers" in data

    def test_member(self, client, auth_headers):
        resp = client.get(
            "/api/v1/dashboard/member",
            headers=self._h(client, auth_headers),
        )
        assert resp.status_code == 200
        data = resp.json()
        for k in (
            "total_members",
            "member_revenue",
            "non_member_revenue",
            "member_ratio",
            "top10",
        ):
            assert k in data


class TestDashboardRBAC:
    """门店对比接口 RBAC"""

    @pytest.fixture(autouse=True)
    def init(self, app):
        pass

    def test_chain_stores_single_forbidden(self, client, auth_headers):
        """single 版用户访问 /chain/stores 应返回 403"""
        resp = client.get(
            "/api/v1/dashboard/chain/stores",
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestLicenseUpgrade:
    """License 升级回归: trial payload 包含新增字段"""

    def test_trial_license_has_new_fields(self, app):
        lic = getattr(app.state, "license", None)
        assert lic is not None
        p = lic.payload
        assert p is not None
        # 新增字段
        assert "store_name" in p
        assert "tier" in p
        assert "max_stores" in p
        assert "price_tier" in p
        assert "module_flags" in p
        mf = p["module_flags"]
        assert "cloud_sync" in mf
        assert "chain_view" in mf
        # trial 默认 single
        assert p["tier"] == "single"
        assert p["type"] == "single"
        assert p["max_stores"] == 1
        # 价格
        assert p["price_tier"]["amount"] == 0
        assert p["price_tier"]["billing"] == "trial"

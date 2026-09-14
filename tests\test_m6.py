"""M6 集团统一下发 + 多门店调拨 + 分账 集成测试"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.chain.settlement_service import SettlementService
from app.application.chain.transfer_service import TransferService
from app.application.inventory.inventory_service import InventoryService
from app.domain.chain.policy_scope import DEFAULT_HQ_PCT, PolicyScope
import uuid as uuid_mod

from app.infra.db.engine import session_factory
from app.infra.db.models import Order, Warehouse
from cloud.main import app as cloud_app
from cloud.models import init_db

# ── Fixtures ────────────────────────────────────────────────-


@pytest.fixture(scope="function")
def cloud_client(tmp_path):
    """云端测试客户端"""
    db_path = str(tmp_path / "test_cloud_m6.db")
    import cloud.main as cm

    cm.SessionLocal = init_db(db_path)
    with TestClient(cloud_app) as c:
        yield c


class TestPolicyScope:
    """策略字段白名单测试"""

    def test_menu_fields_whitelist(self):
        """C-1: 菜单策略白名单覆盖指定字段"""
        payload = {"name": "菜A", "category_id": "c1", "price": 3800,
                   "status": "active", "is_86": 0, "specs_json": "{}",
                   "extra_field": "should_be_filtered"}
        clean = {k: v for k, v in payload.items() if k in PolicyScope.MENU_FIELDS}
        assert "name" in clean
        assert "extra_field" not in clean
        assert len(clean) == 6

    def test_price_fields_whitelist(self):
        """C-2: 价格策略仅允许 price 字段"""
        payload = {"price": 2800, "name": "should_be_filtered"}
        clean = {k: v for k, v in payload.items() if k in PolicyScope.PRICE_FIELDS}
        assert clean == {"price": 2800}

    def test_default_hq_pct(self):
        """默认总部抽成 5%"""
        assert DEFAULT_HQ_PCT == 5


class TestCloudPolicyPush:
    """云端策略推送 ledger 测试"""

    @pytest.fixture(autouse=True)
    def _seed_tenants(self, cloud_client):
        """注册母店 + 子店"""
        from tests.test_cloud import _payload

        cloud_client.post("/cloud/v1/ingest",
                          json={"payload": {
                              **_payload(),
                              "merchant_id": "m_parent_m6",
                              "store_name": "M6母店",
                          }, "sig": "x"})
        cloud_client.post("/cloud/v1/ingest",
                          json={"payload": {
                              **_payload(),
                              "merchant_id": "m_child_m6",
                              "store_name": "M6子店",
                              "parent_merchant_id": "m_parent_m6",
                          }, "sig": "x"})

    def test_push_menu_policy_creates_ledger(self, cloud_client):
        """推送菜单策略应记录到 policy_pushes 并返回 targets"""
        r = cloud_client.post(
            "/cloud/v1/policies/menu?parent_id=m_parent_m6",
            json={"name": "新菜", "price": 2800},
            headers={"Authorization": "Bearer m_parent_m6"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["policy_type"] == "menu"
        # 推送给了 parent + child
        assert len(data["targets"]) >= 2

    def test_policy_pull_returns_incremental(self, cloud_client):
        """拉取策略应返回 since 版本之后的内容"""
        # 先发一条
        cloud_client.post(
            "/cloud/v1/policies/prices?parent_id=m_parent_m6",
            json={"price": 1800},
            headers={"Authorization": "Bearer m_parent_m6"},
        )
        # 用子店 token 拉取
        r = cloud_client.get(
            "/cloud/v1/policies/m_child_m6/pull?since=0",
            headers={"Authorization": "Bearer m_parent_m6"},
        )
        assert r.status_code == 200
        policies = r.json()["policies"]
        assert len(policies) >= 1
        assert policies[0]["policy_type"] == "prices"
        assert policies[0]["version"] == 1

    def test_policy_status_returns_latest_version(self, cloud_client):
        """状态查询返回最新 push_version"""
        cloud_client.post(
            "/cloud/v1/policies/members?parent_id=m_parent_m6",
            json={"level_config": "gold"},
            headers={"Authorization": "Bearer m_parent_m6"},
        )
        r = cloud_client.get(
            "/cloud/v1/policies/m_parent_m6/status",
            headers={"Authorization": "Bearer m_parent_m6"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["latest_versions"].get("members", 0) >= 1


class TestTransferAndSettlement:
    """调拨与分账服务测试"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """初始化仓库与物料"""
        self.inv_svc = InventoryService(merchant_id="local")
        self.inv_svc.init_raw_materials()
        self.transfer_svc = TransferService(merchant_id="local")
        self.settle_svc = SettlementService(merchant_id="local")

        # 直接创建两个仓库（init_warehouse 幂等于 type="main"）
        with session_factory() as s:
            existing = s.query(Warehouse).filter_by(merchant_id="local").all()
            if len(existing) < 2:
                wa = Warehouse(
                    id=uuid_mod.uuid4().hex,
                    merchant_id="local",
                    name="仓库A",
                    type="main",
                )
                wb = Warehouse(
                    id=uuid_mod.uuid4().hex,
                    merchant_id="local",
                    name="仓库B",
                    type="branch",
                )
                s.add(wa)
                s.add(wb)
                s.commit()
                self._wh_a, self._wh_b = wa.id, wb.id
            else:
                self._wh_a, self._wh_b = existing[0].id, existing[1].id

    def _two_warehouses(self) -> tuple[str, str]:
        """获取两个仓库 ID"""
        return self._wh_a, self._wh_b

    def _seed_stock(self, warehouse_id: str, qty: float = 100.0):
        """为仓库A注入原料库存"""
        self.inv_svc.inbound(warehouse_id, "mat_001", qty)

    def test_create_transfer_ship_receive(self):
        """完整调拨流程：create → ship → receive"""
        wh_a, wh_b = self._two_warehouses()
        self._seed_stock(wh_a, 100.0)

        # 创建调拨单
        result = self.transfer_svc.create(
            from_warehouse_id=wh_a,
            to_warehouse_id=wh_b,
            items=[{"material_id": "mat_001", "qty": 30.0, "unit_cost": 800}],
        )
        assert result["status"] == "draft"
        tid = result["id"]

        # 发货
        ship_result = self.transfer_svc.ship(tid)
        assert ship_result["status"] == "shipping"

        # 收货
        recv_result = self.transfer_svc.receive(tid)
        assert recv_result["status"] == "received"

        # 验证库存变化
        stock_a = self.inv_svc.get_stock(wh_a, "mat_001")
        stock_b = self.inv_svc.get_stock(wh_b, "mat_001")
        assert stock_a["qty"] == 70.0
        assert stock_b["qty"] == 30.0

    def test_void_transfer_only_draft(self):
        """仅可废 draft 状态调拨单"""
        wh_a, wh_b = self._two_warehouses()
        self._seed_stock(wh_a, 100.0)
        result = self.transfer_svc.create(
            from_warehouse_id=wh_a,
            to_warehouse_id=wh_b,
            items=[{"material_id": "mat_001", "qty": 10.0}],
        )
        tid = result["id"]

        # 发货后不可废
        self.transfer_svc.ship(tid)
        with pytest.raises(ValueError, match="不可作废"):
            self.transfer_svc.void(tid)

    def test_ship_wrong_status_raises(self):
        """重复发货应报错 (CAS 不匹配)"""
        wh_a, wh_b = self._two_warehouses()
        self._seed_stock(wh_a, 100.0)
        result = self.transfer_svc.create(
            from_warehouse_id=wh_a,
            to_warehouse_id=wh_b,
            items=[{"material_id": "mat_001", "qty": 10.0}],
        )
        tid = result["id"]
        self.transfer_svc.ship(tid)
        with pytest.raises(ValueError, match="状态不可发货"):
            self.transfer_svc.ship(tid)

    def test_settlement_calculate_and_confirm(self):
        """分账计算与确认"""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=1)

        # 先创建一笔订单
        with session_factory() as s:
            order = Order(
                id="order_m6_test",
                order_no="M6001",
                merchant_id="local",
                cashier_id="test_cashier",
                member_id="test_member",
                status="paid",
                final_amount=10000,
                total_amount=10000,
                paid_amount=10000,
                created_at=start + timedelta(hours=1),
            )
            s.add(order)
            s.commit()

        result = self.settle_svc.calculate(
            period_start=start, period_end=now, hq_pct=DEFAULT_HQ_PCT
        )
        assert result["status"] == "draft"
        assert result["total_revenue"] == 10000
        assert result["hq_amount"] == 500  # 5%
        assert result["store_amount"] == 9500

        sid = result["id"]
        confirm_result = self.settle_svc.confirm(sid)
        assert confirm_result["status"] == "confirmed"

    def test_settlement_invalid_hq_pct(self):
        """抽成比例超出范围应报错"""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="超出范围"):
            self.settle_svc.calculate(
                period_start=now - timedelta(days=1),
                period_end=now,
                hq_pct=150,
            )

    def test_list_transfers_and_settlements(self):
        """列表查询返回正确数据"""
        wh_a, wh_b = self._two_warehouses()
        self._seed_stock(wh_a, 100.0)
        self.transfer_svc.create(
            from_warehouse_id=wh_a,
            to_warehouse_id=wh_b,
            items=[{"material_id": "mat_001", "qty": 5.0}],
        )
        transfers = self.transfer_svc.list_transfers()
        assert len(transfers) >= 1
        settlements = self.settle_svc.list_settlements()
        assert isinstance(settlements, list)

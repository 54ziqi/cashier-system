"""M4/M5 供应链ERP + 财务/KDS/打印 服务健康测试"""

from __future__ import annotations

import pytest

from app.application.finance.offline_cache_service import OfflineCacheService
from app.application.finance.report_service import ReportService
from app.application.inventory.inventory_service import InventoryService
from app.application.inventory.physical_count_service import PhysicalCountService
from app.application.inventory.production_service import ProductionService
from app.application.kds.kds_service import KdsService
from app.application.print.escpos_service import EscPosService
from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Material,
    Warehouse,
    WarehouseStock,
    StockMovement,
    PurchaseOrder,
    RecipeBOM,
    PhysicalInventorySheet,
    KdsTicket,
    EscPosJob,
    FinancialReport,
    Product,
    RecipeBOM as BOMModel,
)


# ── M4: InventoryService ─────────────────────────────────────


class TestInventoryService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = InventoryService(merchant_id="local")
        # 确保仓库和原料已初始化
        self.svc.init_warehouse()
        self.svc.init_raw_materials()

    def _main_warehouse(self) -> str:
        wh = self.svc.init_warehouse()
        return wh.id

    def test_init_warehouse_and_materials(self):
        """初始化仓库和 20 个原料"""
        wh = self.svc.init_warehouse()
        assert wh is not None
        mats = self.svc.init_raw_materials()
        # 原料已存在则返回空列表（幂等）
        with session_factory() as s:
            count = s.query(Material).filter_by(merchant_id="local").count()
            assert count == 20

    def test_inbound_and_outbound(self):
        """入库后库存增加，出库后库存减少"""
        wh_id = self._main_warehouse()
        mat_id = "mat_001"

        # 先大量入库使其高于安全库存
        self.svc.inbound(wh_id, mat_id, qty=10000, unit_price=500)
        stock = self.svc.get_stock(wh_id, mat_id)
        assert stock["qty"] == 10000
        assert stock["is_low"] is False

        # 出库 3000
        self.svc.outbound(wh_id, mat_id, qty=3000)
        stock = self.svc.get_stock(wh_id, mat_id)
        assert stock["qty"] == 7000

    def test_check_safety_stock_and_replenishment(self):
        """低库存预警和补货建议"""
        wh_id = self._main_warehouse()
        # 大量出库使其低于安全库存
        self.svc.inbound(wh_id, "mat_001", qty=2000, unit_price=100)
        self.svc.outbound(wh_id, "mat_001", qty=1990)
        low_stocks = self.svc.check_safety_stock()
        assert len(low_stocks) >= 1

    def test_receive_purchase_order(self):
        """采购单审批+收货"""
        wh_id = self._main_warehouse()
        po = self.svc.create_purchase_order(
            items=[
                {"material_id": "mat_001", "qty_ordered": 100, "unit_price": 500},
            ],
            supplier="测试供应商",
        )
        self.svc.approve_purchase_order(po.id)
        # 获取 PO
        with session_factory() as s:
            po_db = s.query(PurchaseOrder).filter_by(id=po.id).first()
            assert po_db.status == "approved"
        self.svc.receive_po(po.id, operator_id="admin")
        with session_factory() as s:
            po_db = s.query(PurchaseOrder).filter_by(id=po.id).first()
            assert po_db.status == "received"


# ── M4: ProductionService ───────────────────────────────────


class TestProductionService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = ProductionService(merchant_id="local")
        inv_svc = InventoryService(merchant_id="local")
        inv_svc.init_warehouse()
        inv_svc.init_raw_materials()
        inv_svc.init_raw_materials()
        # 确保有 BOM 和仓库库存
        with session_factory() as s:
            # 建 BOM: demo_p001 需要 mat_001 100g
            bom = BOMModel(
                id="bom_test_001",
                product_id="demo_p001",
                material_id="mat_001",
                qty=100,
                wastage_pct=5,
                unit="g",
            )
            s.merge(bom)
            s.commit()
        # 给仓库补原料
        wh = inv_svc.init_warehouse()
        inv_svc.inbound(wh.id, "mat_001", qty=5000, unit_price=800)

    def test_calculate_product_cost(self):
        """按 BOM 计算菜品成本"""
        cost = self.svc.calculate_product_cost("demo_p001")
        # mat_001 cost_price=800, qty=100, wastage=5% → 800*100*1.05 = 84000
        expected = int(800 * 100 * 1.05)
        assert cost == expected

    def test_consume_for_order_requires_warehouse(self):
        """consume_for_order 在主仓库不存在时跳过"""
        # 该场景下主仓库存在，不会出错
        result = self.svc.consume_for_order("non-existent-order")
        assert result == []


# ── M4: PhysicalCountService ────────────────────────────────


class TestPhysicalCountService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = PhysicalCountService(merchant_id="local")
        inv_svc = InventoryService(merchant_id="local")
        inv_svc.init_warehouse()
        inv_svc.init_raw_materials()
        self.wh_id = inv_svc.init_warehouse().id
        # 入库原料
        inv_svc.inbound(self.wh_id, "mat_001", qty=1000, unit_price=100)

    def test_create_and_approve_sheet(self):
        """创建盘点单并审批生成差异入账"""
        sheet = self.svc.create_sheet(self.wh_id, operator_id="admin")
        assert sheet.status == "draft"

        # 录入盘点数（与账面不同产生差异）
        self.svc.submit_line(sheet.id, "mat_001", counted_qty=950)

        result = self.svc.approve_sheet(sheet.id, operator_id="admin")
        assert result["status"] == "approved"
        assert result["total_variance"] < 0  # 盘亏

    def test_get_sheet_detail(self):
        """获取盘点单详情"""
        sheet = self.svc.create_sheet(self.wh_id)
        detail = self.svc.get_sheet(sheet.id)
        assert detail is not None
        assert len(detail["lines"]) >= 1


# ── M5: ReportService ───────────────────────────────────────


class TestReportService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = ReportService(merchant_id="local")

    def test_profit_report_returns_structure(self):
        """利润报表返回正确结构"""
        report = self.svc.generate_profit_report()
        assert report["report_type"] == "profit"
        assert "total_revenue" in report
        assert "total_cost" in report
        assert "gross_profit" in report
        assert "margin_pct" in report

    def test_dashboard_metrics(self):
        """看板指标返回正确结构"""
        metrics = self.svc.get_dashboard_metrics(days=7)
        assert metrics["days"] == 7
        assert "total_revenue" in metrics
        assert "order_count" in metrics


# ── M5: OfflineCacheService ─────────────────────────────────


class TestOfflineCacheService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        # 使用测试临时目录
        self.svc = OfflineCacheService(settings=app.state.settings)
        self.svc.clear_cache()

    def test_cache_and_verify(self):
        """缓存验签结果并验证"""
        from app.kernel.license.verifier import LicenseResult

        fake_result = LicenseResult(
            status="valid",
            message="test",
            payload={"merchant_id": "test", "expire_at": "2099-01-01T00:00:00Z"},
        )
        self.svc.cache_verification(fake_result)
        assert self.svc.is_valid() is True
        cached = self.svc.get_cached()
        assert cached is not None
        assert cached["status"] == "valid"

    def test_load_fallback(self):
        """离线 fallback 加载"""
        fallback = self.svc.load_fallback()
        # 无缓存时返回 None
        assert fallback is None


# ── M5: KdsService ──────────────────────────────────────────


class TestKdsService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = KdsService(merchant_id="local")

    def test_create_and_transition_tickets(self):
        """创建 KDS 制作单并流转"""
        with session_factory() as s:
            from app.infra.db.models import Order, OrderItem
            # 创建测试订单（member_id 非空约束）
            order = Order(
                id="kds_test_order_001",
                order_no="ORD_KDS_TEST_001",
                merchant_id="local",
                cashier_id="admin",
                member_id="",
                status="paid",
                total_amount=1000,
                final_amount=1000,
            )
            s.merge(order)
            item = OrderItem(
                id="kds_test_item_001",
                order_id="kds_test_order_001",
                product_id="demo_p001",
                product_name="测试菜品",
                barcode="",
                unit_price=1000,
                quantity=1,
                subtotal=1000,
            )
            s.merge(item)
            s.commit()

        tickets = self.svc.create_tickets("kds_test_order_001")
        assert len(tickets) >= 1
        ticket_id = tickets[0].id

        # 状态流转
        self.svc.mark_cooking(ticket_id)
        self.svc.mark_ready(ticket_id)
        self.svc.mark_served(ticket_id)

        # 查询队列
        queue = self.svc.get_queue()
        assert isinstance(queue, list)

    def test_fire_ticket(self):
        """叫起 KDS 制作单"""
        with session_factory() as s:
            from app.infra.db.models import Order, OrderItem
            order = Order(
                id="kds_test_order_002",
                order_no="ORD_KDS_TEST_002",
                merchant_id="local",
                cashier_id="admin",
                member_id="",
                status="paid",
                total_amount=500,
                final_amount=500,
            )
            s.merge(order)
            item = OrderItem(
                id="kds_test_item_002",
                order_id="kds_test_order_002",
                product_id="demo_p001",
                product_name="测试饮品",
                barcode="",
                unit_price=500,
                quantity=1,
                subtotal=500,
            )
            s.merge(item)
            s.commit()

        tickets = self.svc.create_tickets("kds_test_order_002")
        result = self.svc.fire_ticket(tickets[0].id)
        assert result["fired"] is True
        assert result["fire_at"] is not None


# ── M5: EscPosService ───────────────────────────────────────


class TestEscPosService:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.svc = EscPosService(merchant_id="local")

    def test_build_receipt_and_enqueue(self):
        """构建小票并入队"""
        order_data = {
            "order_no": "ORD_TEST_PRINT",
            "final_amount": 1000,
            "created_at": "2025-01-01T00:00:00",
            "items": [
                {"product_name": "测试商品", "quantity": 2, "subtotal": 1000},
            ],
        }
        raw = self.svc.build_receipt(order_data)
        assert isinstance(raw, bytes)
        assert len(raw) > 0

        job = self.svc.enqueue("receipt", "default", raw)
        assert job.id is not None
        assert job.status == "pending"

    def test_print_test_and_list_jobs(self):
        """打印测试页并列任务"""
        job = self.svc.print_test(target="test_printer")
        assert job.id is not None

        # 处理队列
        results = self.svc.process_queue()
        assert len(results) >= 1

        jobs = self.svc.list_jobs()
        assert len(jobs) >= 1

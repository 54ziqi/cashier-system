"""应用层：库存管理服务 - 仓库/原料/出入库/调拨/采购单收货/补货建议"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Material as MaterialModel,
    PurchaseOrder as PurchaseOrderModel,
    PurchaseOrderItem as PurchaseOrderItemModel,
    StockMovement as StockMovementModel,
    Warehouse as WarehouseModel,
    WarehouseStock as WarehouseStockModel,
)

log = logging.getLogger(__name__)

# ── 20 个示例原料 ──
DEMO_RAW_MATERIALS = [
    ("牛肉", "肉类", "g", 800, 5000, 1000, 7),
    ("猪肉", "肉类", "g", 500, 3000, 500, 7),
    ("鸡肉", "肉类", "g", 300, 4000, 800, 5),
    ("羊肉", "肉类", "g", 900, 2000, 300, 7),
    ("鸭肉", "肉类", "g", 400, 2000, 400, 5),
    ("土豆", "蔬菜", "g", 50, 5000, 1000, 14),
    ("西红柿", "蔬菜", "g", 80, 3000, 600, 7),
    ("青椒", "蔬菜", "g", 100, 2000, 400, 7),
    ("白菜", "蔬菜", "g", 30, 4000, 800, 10),
    ("胡萝卜", "蔬菜", "g", 40, 3000, 500, 14),
    ("食用盐", "调料", "g", 20, 2000, 500, 365),
    ("生抽", "调料", "ml", 150, 1000, 200, 180),
    ("老抽", "调料", "ml", 180, 1000, 200, 180),
    ("料酒", "调料", "ml", 120, 1000, 200, 365),
    ("白糖", "调料", "g", 80, 2000, 500, 365),
    ("一次性餐盒", "包材", "个", 150, 5000, 1000, 730),
    ("筷子", "包材", "双", 30, 5000, 1000, 730),
    ("塑料袋", "包材", "个", 20, 5000, 1000, 730),
    ("纸巾", "包材", "包", 200, 2000, 500, 730),
    ("饮料杯", "包材", "个", 180, 3000, 500, 730),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InventoryService:
    """库存管理服务：出入库/调拨/采购收货/安全库存预警/补货建议"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── 初始化 ──────────────────────────────────────────────

    def init_warehouse(self, name: str = "主仓库") -> WarehouseModel:
        """为租户初始化默认仓库（幂等）"""
        with session_factory() as s:
            existing = (
                s.query(WarehouseModel)
                .filter_by(merchant_id=self.merchant_id, type="main")
                .first()
            )
            if existing:
                return existing
            wh = WarehouseModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=name,
                type="main",
            )
            s.add(wh)
            s.commit()
            s.refresh(wh)
            return wh

    def init_raw_materials(self) -> list[MaterialModel]:
        """为租户初始化 20 个示例原料（幂等）"""
        with session_factory() as s:
            existing_count = (
                s.query(MaterialModel).filter_by(merchant_id=self.merchant_id).count()
            )
            if existing_count > 0:
                return []
            materials = []
            for i, (name, category, unit, cost_price, safety_stock, stock, shelf_life) in enumerate(
                DEMO_RAW_MATERIALS
            ):
                m = MaterialModel(
                    id=f"mat_{i + 1:03d}",
                    merchant_id=self.merchant_id,
                    name=name,
                    category=category,
                    unit=unit,
                    cost_price=cost_price,
                    stock=float(stock),
                    safety_stock=float(safety_stock),
                    shelf_life_days=shelf_life,
                    status="active",
                )
                s.add(m)
                materials.append(m)
            s.commit()
            return materials

    # ── 核心操作 ────────────────────────────────────────────

    def inbound(
        self,
        warehouse_id: str,
        material_id: str,
        qty: float,
        unit_price: int = 0,
        ref_table: str = "",
        ref_id: str = "",
        operator_id: str = "",
    ) -> StockMovementModel:
        """入库：增加仓库库存 + 原料总库存 + 流水记录"""
        with session_factory() as s:
            # 校验仓库归属
            wh = (
                s.query(WarehouseModel)
                .filter_by(id=warehouse_id, merchant_id=self.merchant_id)
                .first()
            )
            if not wh:
                raise ValueError(f"仓库不存在: {warehouse_id}")
            # 校验原料归属
            mat = (
                s.query(MaterialModel)
                .filter_by(id=material_id, merchant_id=self.merchant_id, status="active")
                .first()
            )
            if not mat:
                raise ValueError(f"原料不存在: {material_id}")

            # UPSERT warehouse_stocks
            ws = (
                s.query(WarehouseStockModel)
                .filter_by(warehouse_id=warehouse_id, material_id=material_id)
                .first()
            )
            if not ws:
                ws = WarehouseStockModel(
                    id=str(uuid.uuid4()),
                    warehouse_id=warehouse_id,
                    material_id=material_id,
                    qty=0,
                )
                s.add(ws)

            ws.qty += qty
            mat.stock += qty
            mat.updated_at = _utcnow()

            # 移动加权平均：更新 cost_price
            if unit_price > 0 and qty > 0:
                old_total_cost = mat.cost_price * (mat.stock - qty)
                new_total_cost = unit_price * qty
                mat.cost_price = int((old_total_cost + new_total_cost) / mat.stock)

            # 流水记录
            movement = StockMovementModel(
                id=str(uuid.uuid4()),
                warehouse_id=warehouse_id,
                material_id=material_id,
                type="inbound",
                qty=qty,
                balance_after=ws.qty,
                ref_table=ref_table,
                ref_id=ref_id,
                operator_id=operator_id,
            )
            s.add(movement)
            s.commit()
            s.refresh(movement)
            return movement

    def outbound(
        self,
        warehouse_id: str,
        material_id: str,
        qty: float,
        ref_table: str = "",
        ref_id: str = "",
        operator_id: str = "",
    ) -> StockMovementModel:
        """出库：CAS 原子 UPDATE 防止并发超卖"""
        from sqlalchemy import text

        with session_factory() as s:
            # CAS 原子扣减仓库库存
            result = s.execute(
                text(
                    "UPDATE warehouse_stocks SET qty = qty - :q "
                    "WHERE warehouse_id = :wid AND material_id = :mid AND qty >= :q"
                ),
                {"q": qty, "wid": warehouse_id, "mid": material_id},
            )
            if result.rowcount == 0:
                ws = (
                    s.query(WarehouseStockModel)
                    .filter_by(warehouse_id=warehouse_id, material_id=material_id)
                    .first()
                )
                raise ValueError(
                    f"库存不足: warehouse={warehouse_id} material={material_id} "
                    f"available={ws.qty if ws else 0} required={qty}"
                )

            # 读回最新值
            new_wh_qty = s.execute(
                text("SELECT qty FROM warehouse_stocks WHERE warehouse_id = :wid AND material_id = :mid"),
                {"wid": warehouse_id, "mid": material_id},
            ).fetchone()[0]

            mat = (
                s.query(MaterialModel)
                .filter_by(id=material_id, merchant_id=self.merchant_id)
                .first()
            )
            if not mat:
                raise ValueError(f"原料不存在: {material_id}")
            mat.stock -= qty
            mat.updated_at = _utcnow()

            movement = StockMovementModel(
                id=str(uuid.uuid4()),
                warehouse_id=warehouse_id,
                material_id=material_id,
                type="outbound",
                qty=-qty,
                balance_after=new_wh_qty,
                ref_table=ref_table,
                ref_id=ref_id,
                operator_id=operator_id,
            )
            s.add(movement)
            s.commit()
            s.refresh(movement)
            return movement

    def transfer(
        self,
        from_wh: str,
        to_wh: str,
        material_id: str,
        qty: float,
        operator_id: str = "",
    ) -> dict:
        """调拨：A仓库出库 + B仓库入库"""
        self.outbound(
            warehouse_id=from_wh,
            material_id=material_id,
            qty=qty,
            ref_table="transfer_orders",
            ref_id=f"{from_wh}->{to_wh}",
            operator_id=operator_id,
        )
        self.inbound(
            warehouse_id=to_wh,
            material_id=material_id,
            qty=qty,
            ref_table="transfer_orders",
            ref_id=f"{from_wh}->{to_wh}",
            operator_id=operator_id,
        )
        return {"from": from_wh, "to": to_wh, "material_id": material_id, "qty": qty}

    # ── 查询 ────────────────────────────────────────────────

    def get_stock(self, warehouse_id: str, material_id: str) -> dict:
        """查询单仓库-单物料库存"""
        with session_factory() as s:
            ws = (
                s.query(WarehouseStockModel)
                .filter_by(warehouse_id=warehouse_id, material_id=material_id)
                .first()
            )
            mat = (
                s.query(MaterialModel)
                .filter_by(id=material_id, merchant_id=self.merchant_id)
                .first()
            )
            qty = ws.qty if ws else 0
            return {
                "warehouse_id": warehouse_id,
                "material_id": material_id,
                "material_name": mat.name if mat else "",
                "qty": qty,
                "safety_stock": mat.safety_stock if mat else 0,
                "is_low": qty < (mat.safety_stock if mat else 0),
            }

    def list_stocks(
        self,
        warehouse_id: str = "",
        material_id: str = "",
        low_stock_only: bool = False,
    ) -> list[dict]:
        """查询库存列表（可按仓库/物料筛选 + 仅低库存）"""
        with session_factory() as s:
            query = (
                s.query(
                    WarehouseStockModel,
                    MaterialModel,
                )
                .join(
                    MaterialModel,
                    WarehouseStockModel.material_id == MaterialModel.id,
                )
                .filter(MaterialModel.merchant_id == self.merchant_id)
            )
            if warehouse_id:
                query = query.filter(WarehouseStockModel.warehouse_id == warehouse_id)
            if material_id:
                query = query.filter(WarehouseStockModel.material_id == material_id)

            rows = query.all()
            results = []
            for ws, mat in rows:
                is_low = ws.qty < mat.safety_stock
                if low_stock_only and not is_low:
                    continue
                results.append(
                    {
                        "warehouse_id": ws.warehouse_id,
                        "material_id": ws.material_id,
                        "material_name": mat.name,
                        "category": mat.category,
                        "qty": ws.qty,
                        "safety_stock": mat.safety_stock,
                        "unit": mat.unit,
                        "is_low": is_low,
                    }
                )
            return results

    def check_safety_stock(self) -> list[dict]:
        """返回当前库存低于安全库存的所有物料"""
        return self.list_stocks(low_stock_only=True)

    def suggest_replenishment(self) -> list[dict]:
        """补货建议：(safety_stock - current_qty) + 预估 lead_days 消耗量"""
        LEAD_DAYS = 3
        with session_factory() as s:
            rows = (
                s.query(MaterialModel)
                .filter_by(merchant_id=self.merchant_id, status="active")
                .all()
            )
            suggestions = []
            for mat in rows:
                # 计算日均消耗量（近 30 天出库量 / 30）
                since = _utcnow().timestamp() - 30 * 86400
                total_out = (
                    s.query(
                        text("COALESCE(SUM(ABS(qty)), 0)").label("total_out")
                    )
                    .select_from(StockMovementModel)
                    .filter(
                        StockMovementModel.material_id == mat.id,
                        StockMovementModel.type == "outbound",
                        StockMovementModel.ts
                        >= datetime.fromtimestamp(since, tz=timezone.utc).isoformat(),
                    )
                    .scalar()
                    or 0
                )
                avg_daily = float(total_out) / 30.0
                suggest_qty = mat.safety_stock + avg_daily * LEAD_DAYS - mat.stock
                if suggest_qty > 0:
                    suggestions.append(
                        {
                            "material_id": mat.id,
                            "material_name": mat.name,
                            "current_stock": mat.stock,
                            "safety_stock": mat.safety_stock,
                            "avg_daily_consumption": round(avg_daily, 2),
                            "suggested_qty": round(suggest_qty, 2),
                            "unit": mat.unit,
                        }
                    )
            return suggestions

    # ── 采购单收货 ──────────────────────────────────────────

    def receive_po(self, po_id: str, operator_id: str = "") -> dict:
        """采购单收货：推进 PO 状态 + inbound 所有明细"""
        with session_factory() as s:
            po = s.query(PurchaseOrderModel).filter_by(id=po_id).first()
            if not po:
                raise ValueError(f"采购单不存在: {po_id}")
            if po.status not in ("draft", "approved", "partially_received"):
                raise ValueError(f"采购单状态不可收货: {po.status}")

            # 查找默认仓库
            wh = (
                s.query(WarehouseModel)
                .filter_by(merchant_id=self.merchant_id, type="main")
                .first()
            )
            if not wh:
                raise ValueError("未找到主仓库，请先初始化")

            items = s.query(PurchaseOrderItemModel).filter_by(po_id=po_id).all()
            for item in items:
                remaining = item.qty_ordered - item.qty_received
                if remaining <= 0:
                    continue
                # 入库
                self.inbound(
                    warehouse_id=wh.id,
                    material_id=item.material_id,
                    qty=remaining,
                    unit_price=item.unit_price,
                    ref_table="purchase_orders",
                    ref_id=po_id,
                    operator_id=operator_id,
                )
                # 更新已收数量
                item.qty_received = item.qty_ordered

            # 推进 PO 状态
            po.status = "received"
            po.received_at = _utcnow()
            po.updated_at = _utcnow()
            s.commit()
            return {"po_id": po_id, "status": "received", "items_received": len(items)}

    # ── 采购单 CRUD ─────────────────────────────────────────

    def create_purchase_order(
        self,
        items: list[dict],
        supplier: str = "",
        operator_id: str = "",
        note: str = "",
    ) -> PurchaseOrderModel:
        """创建采购单"""
        with session_factory() as s:
            po = PurchaseOrderModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                supplier=supplier,
                operator_id=operator_id,
                note=note,
                status="draft",
            )
            s.add(po)

            total_amount = 0
            for it in items:
                subtotal = int(it["qty_ordered"]) * int(it.get("unit_price", 0))
                po_item = PurchaseOrderItemModel(
                    id=str(uuid.uuid4()),
                    po_id=po.id,
                    material_id=it["material_id"],
                    qty_ordered=float(it["qty_ordered"]),
                    unit_price=int(it.get("unit_price", 0)),
                    subtotal=subtotal,
                )
                s.add(po_item)
                total_amount += subtotal

            po.total_amount = total_amount
            s.commit()
            s.refresh(po)
            return po

    def approve_purchase_order(self, po_id: str, operator_id: str = "") -> dict:
        """审批采购单"""
        with session_factory() as s:
            po = s.query(PurchaseOrderModel).filter_by(id=po_id).first()
            if not po:
                raise ValueError(f"采购单不存在: {po_id}")
            if po.status != "draft":
                raise ValueError(f"采购单不可审批，当前状态: {po.status}")
            po.status = "approved"
            po.updated_at = _utcnow()
            s.commit()
            return {"po_id": po_id, "status": "approved"}

    def list_purchase_orders(self, status_filter: str = "") -> list[dict]:
        """查询采购单列表"""
        with session_factory() as s:
            query = s.query(PurchaseOrderModel).filter_by(merchant_id=self.merchant_id)
            if status_filter:
                query = query.filter_by(status=status_filter)
            rows = query.order_by(PurchaseOrderModel.created_at.desc()).all()
            return [
                {
                    "id": r.id,
                    "supplier": r.supplier,
                    "total_amount": r.total_amount,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

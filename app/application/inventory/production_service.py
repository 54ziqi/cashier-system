"""应用层：生产消耗服务 - 按 BOM 扣减/归还原料"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Material as MaterialModel,
    OrderItem as OrderItemModel,
    Product as ProductModel,
    RecipeBOM as BOMModel,
    StockMovement as StockMovementModel,
    Warehouse as WarehouseModel,
)

log = logging.getLogger(__name__)

# ── 产品到默认档口映射 (可按 product name 或其他属性区分) ──
# 简化: 所有菜品默认烹调/蒸煮档口
DEFAULT_STATION = "烹调"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductionService:
    """生产消耗服务：订单落库时按 BOM 扣减原料，退款时归还"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def consume_for_order(self, order_id: str, s: Session | None = None) -> list[dict]:
        """
        订单落库时按 BOM 扣减原料（在 checkout 事务内调用）。
        如果传入 s (Session) 则在给定 session 中执行（不 commit）；
        否则使用独立 session_factory 事务并 commit。
        返回消耗明细列表。
        """
        if s is not None:
            return self._do_consume(s, order_id)
        with session_factory() as s:
            result = self._do_consume(s, order_id)
            s.commit()
            return result

    def _do_consume(self, s: Session, order_id: str) -> list[dict]:
        """实际执行 BOM 消耗逻辑（在已有 Session 上操作）"""
        # 获取订单项
        order_items = s.query(OrderItemModel).filter_by(order_id=order_id).all()
        if not order_items:
            return []

        # 查找默认仓库
        wh = (
            s.query(WarehouseModel)
            .filter_by(merchant_id=self.merchant_id, type="main")
            .first()
        )
        if not wh:
            log.warning("未找到主仓库，跳过原料扣减")
            return []

        consumed = []
        for oi in order_items:
            # 查 BOM
            bom_rows = s.query(BOMModel).filter_by(product_id=oi.product_id).all()
            if not bom_rows:
                continue

            for bom in bom_rows:
                # 计算实际消耗量 = BOM数量 * 订单数量 * (1 + 损耗)
                effective_qty = bom.qty * oi.quantity * (1 + bom.wastage_pct / 100.0)
                if effective_qty <= 0:
                    continue

                # 扣减库存
                result = s.execute(
                    text(
                        "UPDATE warehouse_stocks SET qty = qty - :qty "
                        "WHERE warehouse_id = :wid AND material_id = :mid AND qty >= :qty"
                    ),
                    {
                        "qty": effective_qty,
                        "wid": wh.id,
                        "mid": bom.material_id,
                    },
                )
                if result.rowcount == 0:
                    log.warning(
                        f"原料不足，BOM扣减失败: product={oi.product_name} "
                        f"material_id={bom.material_id} needed={effective_qty}"
                    )
                    continue

                # 扣减原料总库存
                s.execute(
                    text(
                        "UPDATE materials SET stock = stock - :qty, updated_at = :now "
                        "WHERE id = :mid"
                    ),
                    {
                        "qty": effective_qty,
                        "now": _utcnow().isoformat(),
                        "mid": bom.material_id,
                    },
                )

                # 读取当前库存作为 balance_after
                bal_row = s.execute(
                    text(
                        "SELECT qty FROM warehouse_stocks "
                        "WHERE warehouse_id = :wid AND material_id = :mid"
                    ),
                    {"wid": wh.id, "mid": bom.material_id},
                ).fetchone()
                balance_after = float(bal_row[0]) if bal_row else 0

                # 流水记录
                mv = StockMovementModel(
                    id=str(uuid.uuid4()),
                    warehouse_id=wh.id,
                    material_id=bom.material_id,
                    type="outbound",
                    qty=-effective_qty,
                    balance_after=balance_after,
                    ref_table="orders",
                    ref_id=order_id,
                    note=f"生产消耗: {oi.product_name} x{oi.quantity}",
                )
                s.add(mv)

                consumed.append(
                    {
                        "material_id": bom.material_id,
                        "product_name": oi.product_name,
                        "consume_qty": round(effective_qty, 2),
                        "balance_after": balance_after,
                    }
                )

        return consumed

    def calculate_product_cost(self, product_id: str) -> int:
        """按 BOM 计算菜品成本（分）。返回总成本(分)"""
        with session_factory() as s:
            bom_rows = s.query(BOMModel).filter_by(product_id=product_id).all()
            if not bom_rows:
                return 0

            total_cost = 0
            for bom in bom_rows:
                mat = (
                    s.query(MaterialModel)
                    .filter_by(id=bom.material_id, merchant_id=self.merchant_id)
                    .first()
                )
                if mat:
                    effective_qty = bom.qty * (1 + bom.wastage_pct / 100.0)
                    total_cost += int(mat.cost_price * effective_qty)

            return total_cost

    def restore_for_refund(self, order_id: str) -> list[dict]:
        """退款时归还原料库存"""
        with session_factory() as s:
            order_items = s.query(OrderItemModel).filter_by(order_id=order_id).all()
            wh = (
                s.query(WarehouseModel)
                .filter_by(merchant_id=self.merchant_id, type="main")
                .first()
            )
            if not wh or not order_items:
                return []

            restored = []
            for oi in order_items:
                bom_rows = s.query(BOMModel).filter_by(product_id=oi.product_id).all()
                for bom in bom_rows:
                    effective_qty = bom.qty * oi.quantity * (1 + bom.wastage_pct / 100.0)
                    if effective_qty <= 0:
                        continue

                    # 归还库存
                    s.execute(
                        text(
                            "UPDATE warehouse_stocks SET qty = qty + :qty "
                            "WHERE warehouse_id = :wid AND material_id = :mid"
                        ),
                        {"qty": effective_qty, "wid": wh.id, "mid": bom.material_id},
                    )
                    s.execute(
                        text(
                            "UPDATE materials SET stock = stock + :qty, updated_at = :now "
                            "WHERE id = :mid"
                        ),
                        {
                            "qty": effective_qty,
                            "now": _utcnow().isoformat(),
                            "mid": bom.material_id,
                        },
                    )

                    bal_row = s.execute(
                        text(
                            "SELECT qty FROM warehouse_stocks "
                            "WHERE warehouse_id = :wid AND material_id = :mid"
                        ),
                        {"wid": wh.id, "mid": bom.material_id},
                    ).fetchone()
                    balance_after = float(bal_row[0]) if bal_row else 0

                    mv = StockMovementModel(
                        id=str(uuid.uuid4()),
                        warehouse_id=wh.id,
                        material_id=bom.material_id,
                        type="inbound",
                        qty=effective_qty,
                        balance_after=balance_after,
                        ref_table="orders",
                        ref_id=order_id,
                        note=f"退款归还: {oi.product_name} x{oi.quantity}",
                    )
                    s.add(mv)
                    restored.append(
                        {
                            "material_id": bom.material_id,
                            "restore_qty": round(effective_qty, 2),
                            "balance_after": balance_after,
                        }
                    )

            s.commit()
            return restored

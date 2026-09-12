"""库存预警 Agent - 基于销售速度预测库存耗尽时间"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.agents.base import BaseAgent

log = logging.getLogger(__name__)


class StockAlertAgent(BaseAgent):
    """
    基于近期销售速度预测库存耗尽时间
    每30分钟运行一次
    """

    def __init__(self, db_path: Optional[Path] = None, interval: float = 1800):
        super().__init__(interval=interval)
        self._sales_velocity: dict[str, float] = {}  # product_id: units/day

    @property
    def name(self) -> str:
        return "stock_alert"

    def tick(self) -> None:
        """重新计算销售速度"""
        try:
            from app.infra.db.engine import session_factory
            from app.infra.db.models import OrderItem as OrderItemModel, Order as OrderModel

            with session_factory() as s:
                # 近7天已支付订单
                since = datetime.now(timezone.utc) - timedelta(days=7)
                order_ids = [
                    row[0] for row in s.query(OrderModel.id).filter(
                        OrderModel.status.in_(["paid", "completed"]),
                        OrderModel.created_at >= since
                    ).all()
                ]

                if not order_ids:
                    self._sales_velocity = {}
                    return

                items = s.query(OrderItemModel).filter(
                    OrderItemModel.order_id.in_(order_ids)
                ).all()

            # 按商品聚合销量
            sales: dict[str, float] = {}
            for item in items:
                sales[item.product_id] = sales.get(item.product_id, 0) + item.quantity

            # 计算日均销量
            velocity: dict[str, float] = {}
            for pid, qty in sales.items():
                velocity[pid] = qty / 7.0  # units per day

            self._sales_velocity = velocity
            log.info(f"Stock velocity updated: {len(velocity)} products tracked")

        except Exception:
            log.exception("StockAlertAgent tick failed")

    def predict_depletion(self, product_id: str, current_stock: float) -> float:
        """
        返回预计耗尽天数
        返回 float('inf') 表示无销售
        """
        velocity = self._sales_velocity.get(product_id, 0)
        if velocity <= 0:
            return float("inf")
        return current_stock / velocity

    def get_low_stock_products(self) -> list[dict]:
        """获取库存不足的商品列表"""
        result = []
        try:
            from app.infra.db.engine import session_factory
            from app.infra.db.models import Product as ProductModel

            with session_factory() as s:
                products = s.query(ProductModel).filter_by(status="active").all()

                for p in products:
                    days = self.predict_depletion(p.id, p.stock)
                    if p.stock < 10 or (days < 3 and days != float("inf")):
                        result.append({
                            "product_id": p.id,
                            "product_name": p.name,
                            "stock": p.stock,
                            "velocity_per_day": round(self._sales_velocity.get(p.id, 0), 2),
                            "days_to_depletion": round(days, 1) if days != float("inf") else "∞",
                            "level": "low" if p.stock < 10 else "warning",
                        })

            log.info(f"Low stock products: {len(result)}")
            return result

        except Exception:
            log.exception("get_low_stock_products failed")
            return []

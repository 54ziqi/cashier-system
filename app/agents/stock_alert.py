"""库存预警 Agent - 基于销售速度预测库存耗尽时间"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
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
        self.db_path = db_path
        self._sales_velocity: dict[str, float] = {}  # product_id: units/day

    @property
    def name(self) -> str:
        return "stock_alert"

    def tick(self) -> None:
        """重新计算销售速度"""
        self._update_velocity()

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
        return []

    def _update_velocity(self) -> None:
        """更新销售速度统计"""
        log.info("更新库存销售速度...")

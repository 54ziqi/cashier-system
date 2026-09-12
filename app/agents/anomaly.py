"""异常检测 Agent - 基于滑动窗口和3σ统计基线"""
from __future__ import annotations
import logging
import statistics
from collections import deque

from app.agents.base import BaseAgent

log = logging.getLogger(__name__)


class AnomalyDetectionAgent(BaseAgent):
    """
    检测异常交易模式:
    - 异常退款频率
    - 异常折扣率
    - 单笔金额异常

    实现: 滑动窗口 + 3-sigma 统计基线
    """

    def __init__(self, window_size: int = 100, interval: float = 300):
        super().__init__(interval=interval)
        self._windows: dict[str, deque] = {}
        self._thresholds: dict[str, tuple[float, float]] = {}
        self._window_size = window_size

    @property
    def name(self) -> str:
        return "anomaly"

    def tick(self) -> None:
        """更新统计基线"""
        try:
            from app.infra.db.engine import session_factory
            from app.infra.db.models import Order as OrderModel

            with session_factory() as s:
                orders = s.query(OrderModel).filter(
                    OrderModel.status.in_(["paid", "completed", "refunded"])
                ).order_by(OrderModel.created_at.desc()).limit(500).all()

                if not orders:
                    return

                # 计算整单金额基线
                amounts = [o.total_amount for o in orders if o.total_amount > 0]
                if len(amounts) >= 10:
                    mean = statistics.mean(amounts)
                    stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
                    self._thresholds["order_amount"] = (mean, stdev)

                # 折扣率基线
                discount_rates = []
                for o in orders:
                    if o.total_amount > 0 and o.discount_amount > 0:
                        rate = o.discount_amount / o.total_amount
                        discount_rates.append(rate)

                if len(discount_rates) >= 10:
                    mean = statistics.mean(discount_rates)
                    stdev = statistics.stdev(discount_rates) if len(discount_rates) > 1 else 0
                    self._thresholds["discount_rate"] = (mean, stdev)

                # 退款率
                refund_count = sum(1 for o in orders if o.status == "refunded")
                refund_rate = refund_count / len(orders) if orders else 0
                self._windows["refund_rate"].append(refund_rate)

                log.info(f"Anomaly baselines updated: {list(self._thresholds.keys())}")

        except Exception:
            log.exception("AnomalyDetectionAgent tick failed")

    def check(self, metric: str, value: float) -> bool:
        """
        检查是否异常
        返回 True 表示异常
        """
        if metric not in self._windows:
            self._windows[metric] = deque(maxlen=self._window_size)

        window = self._windows[metric]
        window.append(value)

        if len(window) < 10:
            return False

        mean = statistics.mean(window)
        stdev = statistics.stdev(window)

        if stdev == 0:
            return abs(value - mean) > 0.01

        z_score = abs(value - mean) / stdev
        return z_score > 3.0

    def record_refund(self, cashier_id: str, amount: float) -> bool:
        """记录退款，返回是否异常"""
        return self.check(f"refund:{cashier_id}", amount)

    def record_discount(self, cashier_id: str, ratio: float) -> bool:
        """记录折扣率，返回是否异常"""
        return self.check(f"discount:{cashier_id}", ratio)

    def check_amount(self, amount: float) -> bool:
        """检查单笔金额是否异常"""
        if "order_amount" not in self._thresholds:
            return False
        mean, stdev = self._thresholds["order_amount"]
        if stdev == 0:
            return abs(amount - mean) > mean * 0.5 if mean > 0 else False
        z_score = abs(amount - mean) / stdev
        return z_score > 3.0

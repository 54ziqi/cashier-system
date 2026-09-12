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
        pass

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

    def record_amount(self, amount: float) -> bool:
        """记录单笔金额，返回是否异常"""
        return self.check("order_amount", amount)

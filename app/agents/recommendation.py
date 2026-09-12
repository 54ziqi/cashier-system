"""商品推荐 Agent - 基于关联规则"""
from __future__ import annotations
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from app.agents.base import BaseAgent

log = logging.getLogger(__name__)


class RecommendationAgent(BaseAgent):
    """
    基于购物车中商品的共现频率推荐关联商品
    实现精简版 Apriori 算法
    """

    def __init__(self, db_path: Optional[Path] = None, interval: float = 600):
        super().__init__(interval=interval)
        self.db_path = db_path
        self._rules: dict[str, list[tuple[str, float]]] = {}
        self._co_occurrence: dict[frozenset[str], int] = Counter()

    @property
    def name(self) -> str:
        return "recommendation"

    def tick(self) -> None:
        """重新计算共现矩阵"""
        self._mine_rules()

    def suggest(self, cart_product_ids: list[str], top_k: int = 3) -> list[str]:
        """
        根据购物车中的商品返回推荐商品ID
        性能目标: < 1ms
        """
        if not cart_product_ids or not self._rules:
            return []

        score: Counter = Counter()
        for pid in cart_product_ids:
            for related_id, confidence in self._rules.get(pid, []):
                if related_id not in cart_product_ids:
                    score[related_id] += confidence

        return [item for item, _ in score.most_common(top_k)]

    def _mine_rules(self) -> None:
        """从历史订单挖掘关联规则"""
        # 实际实现中从数据库读取订单，这里提供接口定义
        # rules: {product_id: [(related_id, confidence), ...]}
        log.info("挖掘商品关联规则...")


class RecommendationAgentStub:
    """
    RecommendationAgent 的桩实现（无数据库环境）
    """

    def suggest(self, cart_product_ids: list[str], top_k: int = 3) -> list[str]:
        return []

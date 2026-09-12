"""商品推荐 Agent - 基于关联规则（共现矩阵）"""
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
        self._co_occurrence: dict[frozenset[str], int] = Counter()
        self._product_counts: Counter = Counter()
        self._rules: dict[str, list[tuple[str, float]]] = {}

    @property
    def name(self) -> str:
        return "recommendation"

    def tick(self) -> None:
        """从订单历史重新计算共现矩阵"""
        try:
            from app.infra.db.engine import session_factory
            from app.infra.db.models import OrderItem as OrderItemModel, Order as OrderModel

            with session_factory() as s:
                # 只取最近的 paid 订单
                order_ids = [
                    row[0] for row in s.query(OrderModel.id).filter(
                        OrderModel.status.in_(["paid", "completed"])
                    ).order_by(OrderModel.created_at.desc()).limit(1000).all()
                ]
                if not order_ids:
                    return

                items = s.query(OrderItemModel).filter(
                    OrderItemModel.order_id.in_(order_ids)
                ).all()

            # 重建共现矩阵
            co_occurrence: dict[frozenset[str], int] = Counter()
            product_counts: Counter = Counter()

            # 按 order 分组
            order_items_map: dict[str, list[str]] = defaultdict(list)
            for item in items:
                order_items_map[item.order_id].append(item.product_id)
                product_counts[item.product_id] += 1

            for product_ids in order_items_map.values():
                unique_ids = list(set(product_ids))
                for i in range(len(unique_ids)):
                    for j in range(i + 1, len(unique_ids)):
                        pair = frozenset([unique_ids[i], unique_ids[j]])
                        co_occurrence[pair] += 1

            self._co_occurrence = co_occurrence
            self._product_counts = product_counts

            # 生成规则
            rules: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for pair, count in co_occurrence.items():
                pids = list(pair)
                if len(pids) == 2:
                    a, b = pids
                    # confidence(a -> b) = count(a,b) / count(a)
                    conf_ab = count / product_counts[a] if product_counts[a] > 0 else 0
                    conf_ba = count / product_counts[b] if product_counts[b] > 0 else 0
                    if conf_ab > 0.01:
                        rules[a].append((b, conf_ab))
                    if conf_ba > 0.01:
                        rules[b].append((a, conf_ba))

            # 按 confidence 降序
            for pid in rules:
                rules[pid].sort(key=lambda x: x[1], reverse=True)

            self._rules = dict(rules)
            log.info(f"Recommendation rules rebuilt: {len(self._rules)} products")

        except Exception:
            log.exception("RecommendationAgent tick failed")

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

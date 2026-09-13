"""应用层：会员标签服务"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.infra.db.engine import session_factory
from app.infra.db.models import MemberTag

log = logging.getLogger(__name__)


class TagError(Exception):
    pass


class TagService:
    """会员标签服务 — 消费后自动提取标签/手动增删/查询"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def consume_order(self, member_id: str, order_data: dict) -> list[dict]:
        """
        消费后自动提取标签
        order_data: {"time": "2024-01-15T19:30:00", "items": [{"category": "...", "spicy_level": 3}], "subtotal": 5800}
        """
        tags_generated = []

        # 时段偏好
        order_time = order_data.get("time", "")
        if order_time:
            try:
                if isinstance(order_time, str):
                    from datetime import datetime as dt
                    hour = dt.fromisoformat(order_time.replace("Z", "+00:00")).hour
                else:
                    hour = order_time.hour

                if 6 <= hour < 10:
                    period = "早餐"
                elif 10 <= hour < 14:
                    period = "午餐"
                elif 17 <= hour < 21:
                    period = "晚餐"
                elif 21 <= hour <= 23:
                    period = "夜宵"
                else:
                    period = "其他"

                tag = self.add_tag(member_id, "时段偏好", period, source="auto")
                tags_generated.append(tag)
            except (ValueError, TypeError):
                pass

        # 品类偏好
        items = order_data.get("items", [])
        categories = set()
        for item in items:
            cat = item.get("category", "")
            if cat:
                categories.add(cat)

        for cat in categories:
            tag = self.add_tag(member_id, "高频品类", cat, source="auto")
            tags_generated.append(tag)

        # 辣度偏好
        for item in items:
            spicy = item.get("spicy_level")
            if spicy and isinstance(spicy, (int, float)) and spicy >= 3:
                self.add_tag(member_id, "辣度偏好", "喜辣", source="auto")
                break

        # 客单价标签
        subtotal = order_data.get("subtotal", 0)
        if subtotal >= 20000:  # 200元以上
            self.add_tag(member_id, "客单价偏好", "高消费", source="auto")
        elif subtotal >= 5000:
            self.add_tag(member_id, "客单价偏好", "中等消费", source="auto")

        return tags_generated

    def add_tag(self, member_id: str, tag: str, value: str = "", source: str = "manual") -> dict:
        """添加标签"""
        with session_factory() as s:
            # 去重：同一 tag+value 不重复插入
            existing = (
                s.query(MemberTag)
                .filter_by(member_id=member_id, tag=tag, value=value or "")
                .first()
            )
            if existing:
                return self._to_dict(existing)

            t = MemberTag(
                id=str(uuid.uuid4()),
                member_id=member_id,
                tag=tag,
                value=value or None,
                source=source,
                ts=datetime.now(timezone.utc),
            )
            s.add(t)
            s.commit()
            return self._to_dict(t)

    def list_tags(self, member_id: str) -> list[dict]:
        with session_factory() as s:
            tags = (
                s.query(MemberTag)
                .filter_by(member_id=member_id)
                .order_by(MemberTag.ts.desc())
                .all()
            )
            return [self._to_dict(t) for t in tags]

    def remove_tag(self, tag_id: str) -> bool:
        with session_factory() as s:
            t = s.query(MemberTag).filter_by(id=tag_id).first()
            if not t:
                raise TagError("标签不存在")
            s.delete(t)
            s.commit()
            return True

    def _to_dict(self, t: MemberTag) -> dict:
        return {
            "id": t.id,
            "member_id": t.member_id,
            "tag": t.tag,
            "value": t.value or "",
            "source": t.source,
            "ts": t.ts.isoformat() if t.ts else "",
        }

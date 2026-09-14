"""应用层：会员等级规则服务"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.domain.membership.member import MemberLevel as DomainMemberLevel
from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Member as MemberModel,
    MemberLevel,
    MemberLevelHistory,
)

log = logging.getLogger(__name__)


class LevelError(Exception):
    pass


class LevelService:
    """会员等级规则服务 — 初始化/升降级/查询"""

    DEFAULT_LEVELS = [
        {
            "name": "普通会员",
            "min_spend": 0,
            "min_points": 0,
            "discount_pct": 0,
            "benefits_json": None,
            "sort_order": 0,
        },
        {
            "name": "白银会员",
            "min_spend": 10000,
            "min_points": 500,
            "discount_pct": 5,
            "benefits_json": None,
            "sort_order": 1,
        },
        {
            "name": "黄金会员",
            "min_spend": 50000,
            "min_points": 2000,
            "discount_pct": 10,
            "benefits_json": None,
            "sort_order": 2,
        },
        {
            "name": "钻石会员",
            "min_spend": 200000,
            "min_points": 5000,
            "discount_pct": 15,
            "benefits_json": None,
            "sort_order": 3,
        },
    ]

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def init_defaults(self, merchant_id: str | None = None) -> list[dict]:
        """初始化4级会员规则"""
        mid = merchant_id or self.merchant_id

        with session_factory() as s:
            existing = (
                s.query(MemberLevel)
                .filter_by(merchant_id=mid)
                .count()
            )
            if existing > 0:
                log.info(f"会员等级已初始化: {mid}, 跳过")
                return self.list_levels()

            created = []
            for level_data in self.DEFAULT_LEVELS:
                lv = MemberLevel(
                    id=str(uuid.uuid4()),
                    merchant_id=mid,
                    name=level_data["name"],
                    min_spend=level_data["min_spend"],
                    min_points=level_data["min_points"],
                    discount_pct=level_data["discount_pct"],
                    benefits_json=level_data["benefits_json"],
                    sort_order=level_data["sort_order"],
                )
                s.add(lv)
                created.append(level_data)

            s.commit()
            log.info(f"初始化会员等级: {mid}, {len(created)}级")
            return self.list_levels()

    def evaluate(self, member_id: str) -> dict:
        """
        根据累计消费/积分判断是否升降级
        返回 {level_changed, from_level, to_level, level_info}
        """
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise LevelError("会员不存在")

            levels = (
                s.query(MemberLevel)
                .filter_by(merchant_id=self.merchant_id)
                .order_by(MemberLevel.sort_order.desc())
                .all()
            )

            if not levels:
                # 使用领域逻辑兜底
                to_level = DomainMemberLevel.calculate(m.points)
                if to_level != m.level:
                    from_level = m.level
                    m.level = to_level
                    hist = MemberLevelHistory(
                        id=str(uuid.uuid4()),
                        member_id=member_id,
                        from_level=from_level,
                        to_level=to_level,
                        reason="领域逻辑回退: 积分阈值计算",
                        ts=datetime.now(timezone.utc),
                    )
                    s.add(hist)
                    s.commit()
                    return {
                        "level_changed": True,
                        "from_level": from_level,
                        "to_level": to_level,
                        "level_info": {"name": to_level},
                    }
                return {
                    "level_changed": False,
                    "from_level": m.level,
                    "to_level": m.level,
                    "level_info": {"name": m.level},
                }

            # 优先匹配最高等级（sort_order desc 已排好序）
            matched = None
            for lv in levels:
                if m.balance >= lv.min_spend or m.points >= lv.min_points:
                    matched = lv
                    break

            to_level_name = matched.name if matched else normal_level_name(levels)

            if to_level_name != m.level:
                from_level = m.level
                m.level = to_level_name

                # 写入历史
                hist = MemberLevelHistory(
                    id=str(uuid.uuid4()),
                    member_id=member_id,
                    from_level=from_level,
                    to_level=to_level_name,
                    reason=f"消费{ m.balance}分/积分{m.points}",
                    ts=datetime.now(timezone.utc),
                )
                s.add(hist)
                s.commit()

                log.info(
                    f"等级变更: member={member_id} {from_level} -> {to_level_name}"
                )
                return {
                    "level_changed": True,
                    "from_level": from_level,
                    "to_level": to_level_name,
                    "level_info": self._level_to_dict(matched) if matched else {"name": to_level_name},
                }

            return {
                "level_changed": False,
                "from_level": m.level,
                "to_level": to_level_name,
                "level_info": self._level_to_dict(matched) if matched else {"name": m.level},
            }

    def list_levels(self) -> list[dict]:
        with session_factory() as s:
            levels = (
                s.query(MemberLevel)
                .filter_by(merchant_id=self.merchant_id)
                .order_by(MemberLevel.sort_order.asc())
                .all()
            )
            return [self._level_to_dict(lv) for lv in levels]

    def get_member_level(self, member_id: str) -> dict:
        """获取会员当前等级信息"""
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise LevelError("会员不存在")

            level = (
                s.query(MemberLevel)
                .filter_by(merchant_id=self.merchant_id, name=m.level)
                .first()
            )
            return {
                "member_id": m.id,
                "level": m.level,
                "balance": m.balance,
                "points": m.points,
                "level_info": self._level_to_dict(level) if level else None,
            }

    def update_level(self, level_id: str, data: dict) -> dict:
        with session_factory() as s:
            lv = (
                s.query(MemberLevel)
                .filter_by(id=level_id, merchant_id=self.merchant_id)
                .first()
            )
            if not lv:
                raise LevelError("等级不存在")

            for key in ("name", "min_spend", "min_points", "discount_pct", "benefits_json", "sort_order"):
                if key in data:
                    setattr(lv, key, data[key])

            s.commit()
            return self._level_to_dict(lv)

    def _level_to_dict(self, lv) -> dict:
        if not lv:
            return {}
        return {
            "id": lv.id,
            "merchant_id": lv.merchant_id,
            "name": lv.name,
            "min_spend": lv.min_spend,
            "min_points": lv.min_points,
            "discount_pct": lv.discount_pct,
            "benefits_json": lv.benefits_json,
            "sort_order": lv.sort_order,
        }


def normal_level_name(levels: list) -> str:
    """找到最低等级名称作为兜底"""
    if not levels:
        return "normal"
    return min(levels, key=lambda lv: lv.sort_order).name

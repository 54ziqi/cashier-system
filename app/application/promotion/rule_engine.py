"""应用层：促销规则引擎"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Coupon,
    PromotionRule,
)

log = logging.getLogger(__name__)


class RuleError(Exception):
    pass


@dataclass
class PromotionResult:
    """促销结果"""
    rule_id: str = ""
    rule_name: str = ""
    rule_type: str = ""
    applied: bool = False
    discount_amount: int = 0
    gift_items: list[dict] = field(default_factory=list)
    coupon_ids: list[str] = field(default_factory=list)
    message: str = ""


class RuleEngine:
    """
    促销规则引擎
    输入：{member_id, items, subtotal, time}
    输出：-applied_rules, discount_amount, gift_items, coupon_ids
    """

    VALID_TYPES = ("full_reduction", "discount", "gift", "time_special", "coupon_grant")

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def evaluate(self, order_context: dict) -> dict:
        """
        评估所有适用促销规则
        order_context: {member_id, items, subtotal, time}
        """
        subtotal = order_context.get("subtotal", 0)
        order_time = order_context.get("time", "")
        member_id = order_context.get("member_id", "")

        applicable_rules = self._get_active_rules()
        results: list[PromotionResult] = []
        total_discount = 0
        all_gifts: list[dict] = []

        for rule in applicable_rules:
            try:
                result = self._evaluate_single(rule, order_context)
                if result.applied:
                    results.append(result)
                    total_discount += result.discount_amount
                    all_gifts.extend(result.gift_items)
            except Exception as e:
                log.warning(f"规则评估异常: rule={rule.id} error={e}")
                continue

        # 防止折扣超过订单金额
        if total_discount > subtotal:
            total_discount = subtotal

        return {
            "applied_rules": [self._result_to_dict(r) for r in results],
            "discount_amount": total_discount,
            "gift_items": all_gifts,
            "coupon_ids": [],
            "original_amount": subtotal,
            "final_amount": subtotal - total_discount,
        }

    def _evaluate_single(
        self, rule: PromotionRule, ctx: dict
    ) -> PromotionResult:
        """评估单条规则"""
        conditions = json.loads(rule.conditions_json or "{}")
        actions = json.loads(rule.actions_json or "{}")

        # 时间窗口检查
        now = datetime.now(timezone.utc)
        if rule.start_at and now < rule.start_at:
            return PromotionResult(applied=False, message="规则未开始")
        if rule.end_at and now > rule.end_at:
            return PromotionResult(applied=False, message="规则已结束")

        # 条件检查
        subtotal = ctx.get("subtotal", 0)
        min_amount = conditions.get("min_amount", 0)
        if subtotal < min_amount:
            return PromotionResult(applied=False, message=f"未达最低消费{min_amount}")

        time_range = conditions.get("time_range")
        if time_range:
            order_time = ctx.get("time", "")
            if not self._check_time_range(order_time, time_range):
                return PromotionResult(applied=False, message="不在活动时间段")

        members_only = conditions.get("members_only", False)
        if members_only and not ctx.get("member_id"):
            return PromotionResult(applied=False, message="仅限会员")

        # 根据类型计算折扣
        discount = 0
        gifts = []
        coupon_ids = []

        if rule.type == "full_reduction":
            # 满减
            thresholds = actions.get("thresholds", [])  # [{amount: 分, reduce: 分}]
            for t in sorted(thresholds, key=lambda x: x["amount"], reverse=True):
                if subtotal >= t["amount"]:
                    discount = t["reduce"]
                    break

        elif rule.type == "discount":
            # 折扣
            pct = actions.get("percentage", 0)
            discount = int(subtotal * pct / 100)

        elif rule.type == "gift":
            # 赠品
            gifts = actions.get("items", [])

        elif rule.type == "time_special":
            # 时段特价
            pct = actions.get("percentage", 0)
            discount = int(subtotal * pct / 100)

        elif rule.type == "coupon_grant":
            # 送券
            coupon_ids = actions.get("coupon_ids", [])

        applied = discount > 0 or len(gifts) > 0 or len(coupon_ids) > 0

        return PromotionResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.type,
            applied=applied,
            discount_amount=discount,
            gift_items=gifts,
            coupon_ids=coupon_ids,
            message="已应用" if applied else "不适用",
        )

    def _check_time_range(self, order_time: str, time_range: dict) -> bool:
        """检查是否在时间范围内"""
        try:
            if not order_time:
                return False
            if isinstance(order_time, str):
                t = datetime.fromisoformat(order_time.replace("Z", "+00:00"))
            else:
                t = order_time
            hour = t.hour
            start_h = time_range.get("start_hour", 0)
            end_h = time_range.get("end_hour", 24)
            return start_h <= hour < end_h
        except Exception:
            return False

    def _get_active_rules(self) -> list[PromotionRule]:
        """获取所有生效规则，按优先级排序"""
        with session_factory() as s:
            return (
                s.query(PromotionRule)
                .filter_by(merchant_id=self.merchant_id, status="active")
                .order_by(PromotionRule.priority.desc())
                .all()
            )

    def _result_to_dict(self, r: PromotionResult) -> dict:
        return {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "rule_type": r.rule_type,
            "applied": r.applied,
            "discount_amount": r.discount_amount,
            "gift_items": r.gift_items,
            "coupon_ids": r.coupon_ids,
            "message": r.message,
        }

    # ── 规则 CRUD ──────────────────────────────────────────────────

    def create_rule(self, data: dict) -> dict:
        rule_type = data.get("type", "")
        if rule_type not in self.VALID_TYPES:
            raise RuleError(f"不支持的规则类型: {rule_type}")

        with session_factory() as s:
            rule = PromotionRule(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=data["name"],
                type=rule_type,
                priority=data.get("priority", 0),
                conditions_json=json.dumps(data.get("conditions", {})),
                actions_json=json.dumps(data.get("actions", {})),
                start_at=data.get("start_at"),
                end_at=data.get("end_at"),
                stackable=data.get("stackable", 0),
                status=data.get("status", "active"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            s.add(rule)
            s.commit()
            return self._rule_to_dict(rule)

    def update_rule(self, rule_id: str, data: dict) -> dict:
        with session_factory() as s:
            rule = (
                s.query(PromotionRule)
                .filter_by(id=rule_id, merchant_id=self.merchant_id)
                .first()
            )
            if not rule:
                raise RuleError("规则不存在")

            if "name" in data:
                rule.name = data["name"]
            if "priority" in data:
                rule.priority = data["priority"]
            if "conditions" in data:
                rule.conditions_json = json.dumps(data["conditions"])
            if "actions" in data:
                rule.actions_json = json.dumps(data["actions"])
            if "status" in data:
                rule.status = data["status"]
            if "start_at" in data:
                rule.start_at = data["start_at"]
            if "end_at" in data:
                rule.end_at = data["end_at"]
            if "stackable" in data:
                rule.stackable = data["stackable"]

            rule.updated_at = datetime.now(timezone.utc)
            s.commit()
            return self._rule_to_dict(rule)

    def delete_rule(self, rule_id: str) -> bool:
        with session_factory() as s:
            rule = (
                s.query(PromotionRule)
                .filter_by(id=rule_id, merchant_id=self.merchant_id)
                .first()
            )
            if not rule:
                raise RuleError("规则不存在")
            s.delete(rule)
            s.commit()
            return True

    def toggle_rule(self, rule_id: str) -> dict:
        with session_factory() as s:
            rule = (
                s.query(PromotionRule)
                .filter_by(id=rule_id, merchant_id=self.merchant_id)
                .first()
            )
            if not rule:
                raise RuleError("规则不存在")

            rule.status = "inactive" if rule.status == "active" else "active"
            rule.updated_at = datetime.now(timezone.utc)
            s.commit()
            return self._rule_to_dict(rule)

    def list_rules(self, status: str = "active") -> list[dict]:
        with session_factory() as s:
            q = s.query(PromotionRule).filter_by(merchant_id=self.merchant_id)
            if status != "all":
                q = q.filter_by(status=status)
            rules = q.order_by(PromotionRule.priority.desc()).all()
            return [self._rule_to_dict(r) for r in rules]

    def apply_coupon(self, code: str, order_context: dict) -> PromotionResult:
        """在订单中应用优惠券"""
        code_upper = code.upper()
        with session_factory() as s:
            coupon = (
                s.query(Coupon)
                .filter_by(code=code_upper)
                .first()
            )
            if not coupon:
                return PromotionResult(applied=False, message="优惠券不存在")
            if coupon.status != "unused":
                return PromotionResult(applied=False, message=f"优惠券状态异常: {coupon.status}")

            from app.infra.db.models import CouponTemplate
            tpl = (
                s.query(CouponTemplate)
                .filter_by(id=coupon.template_id)
                .first()
            )
            if not tpl:
                return PromotionResult(applied=False, message="券模板不存在")

            subtotal = order_context.get("subtotal", 0)
            if subtotal < tpl.min_amount:
                return PromotionResult(
                    applied=False, message=f"未达最低消费{tpl.min_amount}分"
                )

            discount = 0
            if tpl.type == "amount":
                discount = tpl.value
            elif tpl.type == "percentage":
                discount = int(subtotal * tpl.value / 100)

            return PromotionResult(
                rule_type="coupon",
                applied=True,
                discount_amount=discount,
                coupon_ids=[coupon.id],
                message=f"优惠券抵扣{discount}分",
            )

    def _rule_to_dict(self, rule: PromotionRule) -> dict:
        return {
            "id": rule.id,
            "merchant_id": rule.merchant_id,
            "name": rule.name,
            "type": rule.type,
            "priority": rule.priority,
            "conditions": json.loads(rule.conditions_json or "{}"),
            "actions": json.loads(rule.actions_json or "{}"),
            "start_at": rule.start_at.isoformat() if rule.start_at else None,
            "end_at": rule.end_at.isoformat() if rule.end_at else None,
            "stackable": rule.stackable,
            "status": rule.status,
            "created_at": rule.created_at.isoformat() if rule.created_at else "",
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else "",
        }

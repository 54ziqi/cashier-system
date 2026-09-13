"""应用层：优惠券服务"""

from __future__ import annotations

import json
import logging
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from app.infra.db.engine import session_factory
from app.infra.db.models import Coupon, CouponTemplate

log = logging.getLogger(__name__)


class CouponError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert offset-aware datetime to naive UTC for SQLite compatibility"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


class CouponService:
    """优惠券服务 — 模板管理/发放/核销/过期"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── 模板 CRUD ──────────────────────────────────────────────────

    def create_template(self, data: dict) -> dict:
        coupon_type = data.get("type", "")
        if coupon_type not in ("amount", "percentage"):
            raise CouponError(f"不支持的券类型: {coupon_type}")

        with session_factory() as s:
            tpl = CouponTemplate(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=data["name"],
                type=coupon_type,
                value=data["value"],
                min_amount=data.get("min_amount", 0),
                total_qty=data.get("total_qty", 0),
                issued_qty=0,
                used_qty=0,
                valid_days=data.get("valid_days", 30),
                applicable_products_json=json.dumps(
                    data.get("applicable_products", [])
                ) if "applicable_products" in data else None,
                status=data.get("status", "active"),
                created_at=_utcnow(),
            )
            s.add(tpl)
            s.commit()
            log.info(f"创建券模板: {tpl.name} type={tpl.type} value={tpl.value}")
            return self._tpl_to_dict(tpl)

    def list_templates(self, status: str = "active") -> list[dict]:
        with session_factory() as s:
            q = s.query(CouponTemplate).filter_by(merchant_id=self.merchant_id)
            if status != "all":
                q = q.filter_by(status=status)
            templates = q.order_by(CouponTemplate.created_at.desc()).all()
            return [self._tpl_to_dict(t) for t in templates]

    def get_template(self, template_id: str) -> dict | None:
        with session_factory() as s:
            t = (
                s.query(CouponTemplate)
                .filter_by(id=template_id, merchant_id=self.merchant_id)
                .first()
            )
            return self._tpl_to_dict(t) if t else None

    # ── 实例发放 ──────────────────────────────────────────────────

    def issue(self, template_id: str, member_id: str) -> Coupon:
        """生成唯一 code 并发放"""
        code = "CP" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=10)
        )
        return self._issue_with_code(template_id, member_id, code)

    def _issue_with_code(self, template_id: str, member_id: str, code: str) -> Coupon:
        code_upper = code.upper()
        with session_factory() as s:
            tpl = (
                s.query(CouponTemplate)
                .filter_by(id=template_id, merchant_id=self.merchant_id)
                .first()
            )
            if not tpl:
                raise CouponError("券模板不存在")

            if tpl.total_qty > 0:
                issued_count = (
                    s.query(Coupon).filter_by(template_id=template_id).count()
                )
                if issued_count >= tpl.total_qty:
                    raise CouponError("优惠券已达发放上限")

            # 检查 code 唯一性
            (
                s.query(Coupon).filter_by(code=code_upper).first()
            )

            coupon = Coupon(
                id=str(uuid.uuid4()),
                template_id=template_id,
                member_id=member_id,
                code=code_upper,
                status="unused",
                issued_at=_utcnow(),
            )

            # 唯一性检查
            existing = (
                s.query(Coupon).filter_by(code=code_upper).first()
            )
            if existing:
                raise CouponError("优惠券码已存在,请重试")

            s.add(coupon)
            tpl.issued_qty += 1
            s.commit()
            log.info(f"发券: template={template_id} member={member_id} code={code_upper}")
            return coupon

    # ── 核销 ──────────────────────────────────────────────────────

    def redeem(self, code: str, order_id: str) -> dict:
        """核销: unused → used — CAS 原子操作防止并发双扣"""
        code_upper = code.upper()
        with session_factory() as s:
            from sqlalchemy import text

            # 先校验券码存在性和模板有效期（只读查询）
            coupon = (
                s.query(Coupon).filter_by(code=code_upper).first()
            )
            if not coupon:
                raise CouponError("优惠券不存在")
            if coupon.status == "used":
                raise CouponError("优惠券已使用")
            if coupon.status == "expired":
                raise CouponError("优惠券已过期")

            # CAS 原子核销：仅当 status=unused 时才更新，rowcount=0 表示并发冲突或状态不符
            now = _utcnow()
            result = s.execute(
                text(
                    "UPDATE coupons SET status = 'used', used_at = :now, "
                    "ref_order_id = :oid "
                    "WHERE code = :code AND status = 'unused'"
                ),
                {"now": now, "oid": order_id, "code": code_upper},
            )
            if result.rowcount == 0:
                # 并发冲突：另一个请求已先核销
                raise CouponError("优惠券已被使用或状态已变更")

            # 更新券模板使用量
            s.execute(
                text("UPDATE coupon_templates SET used_qty = used_qty + 1 WHERE id = :tid"),
                {"tid": coupon.template_id},
            )
            s.commit()

            # 脱敏打印券码前4后2位
            masked = code_upper[:4] + "****" + code_upper[-2:] if len(code_upper) > 6 else "****"
            log.info(f"核销: code={masked} order={order_id}")
            return {
                "coupon_id": coupon.id,
                "template_id": coupon.template_id,
                "code": coupon.code,
                "status": "used",
                "order_id": order_id,
            }

    # ── 查询 ──────────────────────────────────────────────────────

    def list_member_coupons(self, member_id: str, status: str = "unused") -> list[dict]:
        with session_factory() as s:
            q = s.query(Coupon).filter_by(member_id=member_id)
            if status != "all":
                q = q.filter_by(status=status)
            coupons = q.order_by(Coupon.issued_at.desc()).all()
            result = []
            for c in coupons:
                tpl = (
                    s.query(CouponTemplate)
                    .filter_by(id=c.template_id)
                    .first()
                )
                result.append({
                    "id": c.id,
                    "template_id": c.template_id,
                    "template_name": tpl.name if tpl else "",
                    "code": c.code,
                    "status": c.status,
                    "type": tpl.type if tpl else "",
                    "value": tpl.value if tpl else 0,
                    "min_amount": tpl.min_amount if tpl else 0,
                    "issued_at": c.issued_at.isoformat() if c.issued_at else "",
                    "used_at": c.used_at.isoformat() if c.used_at else "",
                    "ref_order_id": c.ref_order_id,
                })
            return result

    def validate_coupon(self, code: str, order_context: dict | None = None) -> dict:
        """核销前校验"""
        code_upper = code.upper()
        with session_factory() as s:
            coupon = (
                s.query(Coupon).filter_by(code=code_upper).first()
            )
            if not coupon:
                return {"valid": False, "reason": "优惠券不存在"}

            if coupon.status == "used":
                return {"valid": False, "reason": "优惠券已使用"}
            if coupon.status == "expired":
                return {"valid": False, "reason": "优惠券已过期"}

            tpl = (
                s.query(CouponTemplate)
                .filter_by(id=coupon.template_id)
                .first()
            )
            if not tpl:
                return {"valid": False, "reason": "券模板不存在"}

            # 校验有效期
            if tpl.valid_days > 0:
                expire_at = _to_naive_utc(coupon.issued_at) + timedelta(days=tpl.valid_days)
                if _utcnow().replace(tzinfo=None) > expire_at:
                    return {"valid": False, "reason": "优惠券已过期"}

            # 校验最低消费
            if order_context:
                subtotal = order_context.get("subtotal", 0)
                if subtotal < tpl.min_amount:
                    return {
                        "valid": False,
                        "reason": f"未达最低消费{tpl.min_amount}分",
                    }

            return {
                "valid": True,
                "coupon_id": coupon.id,
                "type": tpl.type,
                "value": tpl.value,
                "min_amount": tpl.min_amount,
                "template_name": tpl.name,
            }

    def expire_coupons(self) -> int:
        """定时: 超过 valid_days → expired"""
        now = _utcnow().replace(tzinfo=None)
        expired_count = 0

        with session_factory() as s:
            unused = (
                s.query(Coupon)
                .filter_by(status="unused")
                .all()
            )

            for c in unused:
                tpl = (
                    s.query(CouponTemplate)
                    .filter_by(id=c.template_id)
                    .first()
                )
                if tpl and tpl.valid_days > 0:
                    expire_at = _to_naive_utc(c.issued_at) + timedelta(days=tpl.valid_days)
                    if now > expire_at:
                        c.status = "expired"
                        expired_count += 1

            s.commit()

        if expired_count > 0:
            log.info(f"过期券: {expired_count}张")
        return expired_count

    # ── helpers ────────────────────────────────────────────────────

    def _tpl_to_dict(self, tpl: CouponTemplate) -> dict:
        return {
            "id": tpl.id,
            "merchant_id": tpl.merchant_id,
            "name": tpl.name,
            "type": tpl.type,
            "value": tpl.value,
            "min_amount": tpl.min_amount,
            "total_qty": tpl.total_qty,
            "issued_qty": tpl.issued_qty,
            "used_qty": tpl.used_qty,
            "valid_days": tpl.valid_days,
            "applicable_products": json.loads(tpl.applicable_products_json)
            if tpl.applicable_products_json
            else [],
            "status": tpl.status,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else "",
        }

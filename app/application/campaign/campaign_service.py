"""应用层：营销活动服务"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    CampaignTask,
    Coupon,
    CouponTemplate,
    Member as MemberModel,
)

log = logging.getLogger(__name__)


class CampaignError(Exception):
    pass


class CampaignService:
    """营销活动服务 — 生日/沉睡/发券"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def check_birthday(self) -> list[dict]:
        """返回明天过生日的会员"""
        tomorrow = (date.today() + timedelta(days=1)).strftime("%m-%d")
        with session_factory() as s:
            # SQLite: members 表暂无 birthday 列返回空（待后续迁移补充 birthday 列）
            # 若无 birthday 列则返回空（待后续迁移补充 birthday 列）
            members = s.execute(
                text(
                    "SELECT id, name, phone FROM members "
                    "WHERE merchant_id = :mid "
                    "AND (substr(birthday, 6, 5) = :md OR birthday = :md2)"
                ),
                {
                    "mid": self.merchant_id,
                    "md": tomorrow,
                    "md2": (date.today() + timedelta(days=1)).isoformat(),
                },
            ).fetchall()

            return [
                {"id": m[0], "name": m[1], "phone": m[2], "birthday": tomorrow}
                for m in members
            ]

    def check_dormant(self, days: int = 30) -> list[dict]:
        """返回 N 天未来店的会员"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        with session_factory() as s:
            members = s.execute(
                text(
                    "SELECT m.id, m.name, m.phone, m.level "
                    "FROM members m "
                    "WHERE m.merchant_id = :mid "
                    "AND m.created_at < :cutoff "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM orders o "
                    "  WHERE o.member_id = m.id AND o.created_at >= :cutoff"
                    ")"
                ),
                {"mid": self.merchant_id, "cutoff": cutoff_iso},
            ).fetchall()

            return [
                {
                    "id": m[0],
                    "name": m[1],
                    "phone": m[2],
                    "level": m[3],
                    "dormant_days": days,
                }
                for m in members
            ]

    def issue_coupon(
        self,
        template_id: str,
        member_id: str,
        code: str | None = None,
    ) -> Coupon:
        """发放优惠券"""
        import random
        import string

        if not code:
            code = "CP" + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )

        with session_factory() as s:
            tpl = (
                s.query(CouponTemplate)
                .filter_by(id=template_id, merchant_id=self.merchant_id)
                .first()
            )
            if not tpl:
                raise CampaignError("优惠券模板不存在")

            member = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not member:
                raise CampaignError("会员不存在")

            # 校验总量
            if tpl.total_qty > 0:
                issued_count = (
                    s.query(Coupon).filter_by(template_id=template_id).count()
                )
                if issued_count >= tpl.total_qty:
                    raise CampaignError("优惠券已达发放上限")

            coupon = Coupon(
                id=str(uuid.uuid4()),
                template_id=template_id,
                member_id=member_id,
                code=code.upper(),
                status="unused",
                issued_at=datetime.now(timezone.utc),
            )
            s.add(coupon)
            tpl.issued_qty += 1
            s.commit()
            log.info(f"发券成功: template={template_id} member={member_id} code={code}")
            return coupon

    def push_campaign(self, coupon: Coupon, campaign_type: str = "manual") -> CampaignTask:
        """写入 campaign_tasks 表"""
        with session_factory() as s:
            task = CampaignTask(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                campaign_type=campaign_type,
                member_id=coupon.member_id,
                coupon_id=coupon.id,
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            s.add(task)
            s.commit()
            log.info(f"营销任务创建: type={campaign_type} member={coupon.member_id}")
            return task

    def send_batch_coupons(
        self,
        template_id: str,
        member_ids: list[str],
        campaign_type: str = "manual",
    ) -> list[dict]:
        """批量发券"""
        results = []
        for member_id in member_ids:
            try:
                coupon = self.issue_coupon(template_id, member_id)
                task = self.push_campaign(coupon, campaign_type)
                results.append({
                    "member_id": member_id,
                    "status": "success",
                    "coupon_id": coupon.id,
                    "code": coupon.code,
                    "task_id": task.id,
                })
            except Exception as e:
                results.append({
                    "member_id": member_id,
                    "status": "failed",
                    "error": str(e),
                })
        return results

"""M6 应用层：集团分账结算服务"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func

from app.domain.chain.policy_scope import DEFAULT_HQ_PCT
from app.infra.db.engine import session_factory
from app.infra.db.models import Order
from app.infra.db.models import Settlement as SettlementModel

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SettlementService:
    """集团分账结算服务：计算 / 确认 / 列表"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def calculate(
        self,
        period_start: datetime,
        period_end: datetime,
        hq_pct: int = DEFAULT_HQ_PCT,
    ) -> dict:
        """
        读 orders 表计算期间收入，生成分账结算单。

        Args:
            period_start: 账期开始时间
            period_end: 账期结束时间
            hq_pct: 总部抽成百分比 (0-100)
        """
        if hq_pct < 0 or hq_pct > 100:
            raise ValueError(f"抽成比例超出范围: {hq_pct} (应在 0-100)")

        with session_factory() as s:
            # 从 orders 表直接 SQL 读收入
            total_revenue = (
                s.query(func.coalesce(func.sum(Order.final_amount), 0))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= period_start,
                    Order.created_at < period_end,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )

            hq_amount = int(total_revenue * hq_pct / 100)
            store_amount = total_revenue - hq_amount

            snapshot = {
                "hq_pct": hq_pct,
                "source": "orders",
                "paid_statuses": ["paid", "completed"],
            }

            settlement = SettlementModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                period_start=period_start,
                period_end=period_end,
                total_revenue=total_revenue,
                hq_amount=hq_amount,
                store_amount=store_amount,
                status="draft",
                config_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            )
            s.add(settlement)
            s.commit()
            s.refresh(settlement)

            return self._to_dict(settlement)

    def confirm(self, settlement_id: str) -> dict:
        """确认分账结算单：draft → confirmed"""
        with session_factory() as s:
            settlement = (
                s.query(SettlementModel).filter_by(id=settlement_id).first()
            )
            if not settlement:
                raise ValueError(f"结算单不存在: {settlement_id}")
            if settlement.merchant_id != self.merchant_id:
                raise ValueError("无权操作该结算单")
            if settlement.status != "draft":
                raise ValueError(
                    f"结算单状态不可确认: {settlement.status}"
                )

            settlement.status = "confirmed"
            settlement.updated_at = _utcnow()
            s.commit()
            return self._to_dict(settlement)

    def list_settlements(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> list[dict]:
        """列出结算单"""
        with session_factory() as s:
            q = s.query(SettlementModel).filter_by(
                merchant_id=self.merchant_id
            )
            if period_start:
                q = q.filter(SettlementModel.period_start >= period_start)
            if period_end:
                q = q.filter(SettlementModel.period_end <= period_end)
            rows = q.order_by(SettlementModel.created_at.desc()).all()
            return [self._to_dict(t) for t in rows]

    # ── 内联序列化 ─────────────────────────────────────────

    def _to_dict(self, t: SettlementModel) -> dict:
        return {
            "id": t.id,
            "merchant_id": t.merchant_id,
            "period_start": t.period_start.isoformat() if t.period_start else None,
            "period_end": t.period_end.isoformat() if t.period_end else None,
            "total_revenue": t.total_revenue,
            "hq_amount": t.hq_amount,
            "store_amount": t.store_amount,
            "status": t.status,
            "config_snapshot_json": t.config_snapshot_json or "",
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }

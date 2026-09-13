"""应用层：会员积分服务"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.db.engine import session_factory
from app.infra.db.models import Member as MemberModel, MemberPointsTxn

log = logging.getLogger(__name__)

# 积分规则：每消费100分（1元）得1积分
POINTS_PER_100_CENTS = 1
# 兑换比例：100积分=1元(100分)
CASH_PER_100_POINTS = 100


class PointsError(Exception):
    pass


class PointsService:
    """会员积分服务 — 赚取/兑换/过期/查询"""

    def __init__(self, merchant_id: str = "local", session: Session | None = None):
        self.merchant_id = merchant_id
        self._ext_session = session

    def _get_session(self) -> Session:
        """获取 session：外部注入 or 工厂创建"""
        if self._ext_session is not None:
            return self._ext_session
        return session_factory()

    def _owns_session(self) -> bool:
        return self._ext_session is None

    def earn(
        self,
        member_id: str,
        amount_spent: int,
        ref_table: str = "",
        ref_id: str = "",
    ) -> dict:
        """
        按消费赚取积分 — 每消费100分（1元）得1积分
        amount_spent: 消费金额（分）
        """
        if amount_spent <= 0:
            raise PointsError("消费金额必须为正数")

        points = amount_spent // 100
        owns_session = self._owns_session()

        if points <= 0:
            return {"points_earned": 0, "total_points": self.get_points(member_id)}

        s = self._get_session()
        try:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise PointsError("会员不存在")

            m.points += points

            txn = MemberPointsTxn(
                id=str(uuid.uuid4()),
                member_id=member_id,
                type="earn",
                points=points,
                ref_table=ref_table or None,
                ref_id=ref_id or None,
                note=f"消费{amount_spent}分,赚取{points}积分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn)
            if owns_session:
                s.commit()

            log.info(f"积分赚取: member={member_id} +{points} points={m.points}")
            return {
                "txn_id": txn.id,
                "points_earned": points,
                "total_points": m.points,
            }
        finally:
            if owns_session:
                s.close()

    def redeem(
        self,
        member_id: str,
        points: int,
        ref_table: str = "",
        ref_id: str = "",
    ) -> dict:
        """
        积分抵扣 — 100积分=1元（100分）
        返回抵扣金额（分）
        """
        if points <= 0:
            raise PointsError("兑换积分必须为正数")

        owns_session = self._owns_session()
        s = self._get_session()
        try:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise PointsError("会员不存在")
            if m.points < points:
                raise PointsError(
                    f"积分不足: 当前{m.points}, 需要{points}"
                )

            m.points -= points
            # 折算抵扣金额
            cash_cents = (points // 100) * CASH_PER_100_POINTS

            txn = MemberPointsTxn(
                id=str(uuid.uuid4()),
                member_id=member_id,
                type="redeem",
                points=-points,
                ref_table=ref_table or None,
                ref_id=ref_id or None,
                note=f"兑换{points}积分,抵扣{cash_cents}分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn)
            if owns_session:
                s.commit()

            log.info(
                f"积分兑换: member={member_id} -{points}积分 抵扣{cash_cents}分"
            )
            return {
                "txn_id": txn.id,
                "points_redeemed": points,
                "cash_cents": cash_cents,
                "total_points": m.points,
            }
        finally:
            if owns_session:
                s.close()

    def expire_points(self, current_ts: datetime | None = None) -> int:
        """过期 12 月前(含)的积分 — 定时任务调用"""
        if current_ts is None:
            current_ts = datetime.now(timezone.utc)

        cutoff = current_ts - timedelta(days=365)
        total_expired = 0

        with session_factory() as s:
            # 找出有正积分且有过期积分的会员
            members = s.query(MemberModel).filter(
                MemberModel.points > 0,
                MemberModel.merchant_id == self.merchant_id,
            ).all()

            for m in members:
                # 计算截止前的累计获得积分
                earn_sum = self._sum_txns_before(s, m.id, "earn", cutoff)
                redeem_sum = abs(self._sum_txns_before(s, m.id, "redeem", cutoff))
                redeem_adjust = abs(
                    self._sum_txns_before(s, m.id, "adjust", cutoff, only_negative=True)
                )

                historical_max = earn_sum
                historical_used = redeem_sum + redeem_adjust
                expired = max(0, historical_max - historical_used)

                # 实际过期数 = min(过期积分, 当前剩余积分)
                actual_expire = min(expired, m.points)
                if actual_expire > 0:
                    m.points -= actual_expire
                    txn = MemberPointsTxn(
                        id=str(uuid.uuid4()),
                        member_id=m.id,
                        type="expire",
                        points=-actual_expire,
                        note=f"过期12月前未使用积分: {actual_expire}",
                        ts=current_ts,
                    )
                    s.add(txn)
                    total_expired += actual_expire

            s.commit()

        if total_expired > 0:
            log.info(f"积分过期完成: 共过期{total_expired}积分")
        return total_expired

    def _sum_txns_before(
        self,
        s: Session,
        member_id: str,
        txn_type: str,
        cutoff: datetime,
        only_negative: bool = False,
    ) -> int:
        """统计某类型流水在 cutoff 前的积分总和"""
        q = (
            s.query(MemberPointsTxn)
            .filter(
                MemberPointsTxn.member_id == member_id,
                MemberPointsTxn.type == txn_type,
                MemberPointsTxn.ts < cutoff,
            )
        )
        total = 0
        for t in q.all():
            if only_negative and t.points < 0:
                total += abs(t.points)
            elif not only_negative:
                total += abs(t.points)
        return total

    def get_points(self, member_id: str) -> int:
        s = self._get_session()
        owns_session = self._owns_session()
        try:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise PointsError("会员不存在")
            return m.points
        finally:
            if owns_session:
                s.close()

    def list_txns(self, member_id: str, limit: int = 50) -> list[dict]:
        with session_factory() as s:
            txns = (
                s.query(MemberPointsTxn)
                .filter_by(member_id=member_id)
                .order_by(MemberPointsTxn.ts.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": t.id,
                    "type": t.type,
                    "points": t.points,
                    "ref_table": t.ref_table,
                    "ref_id": t.ref_id,
                    "note": t.note,
                    "ts": t.ts.isoformat() if t.ts else "",
                }
                for t in txns
            ]

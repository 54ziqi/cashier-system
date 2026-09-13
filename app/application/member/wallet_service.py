"""应用层：会员储值钱包服务"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.infra.db.engine import session_factory
from app.infra.db.models import Member as MemberModel, MemberWalletTxn

log = logging.getLogger(__name__)


class WalletError(Exception):
    pass


class WalletService:
    """会员储值钱包服务 — 充值/扣减/退款/查询"""

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

    def deposit(
        self,
        member_id: str,
        amount: int,
        operator_id: str = "",
        ref_table: str = "",
        ref_id: str = "",
        note: str = "",
        gift_rule: dict | None = None,
    ) -> dict:
        """
        储值充值（带赠送规则）
        amount: 实付金额（分）
        gift_rule: {"threshold": 分, "gift": 分} — 满 threshold 送 gift
        """
        if amount <= 0:
            raise WalletError("充值金额必须为正数")

        gift = 0
        if gift_rule:
            threshold = gift_rule.get("threshold", 0)
            if amount >= threshold:
                gift = gift_rule.get("gift", 0)

        total = amount + gift
        owns_session = self._owns_session()
        s = self._get_session()
        try:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise WalletError("会员不存在")

            old_balance = m.balance
            m.balance += total

            # 写入流水
            txn = MemberWalletTxn(
                id=str(uuid.uuid4()),
                member_id=member_id,
                type="deposit",
                amount=total,
                balance_after=m.balance,
                ref_table=ref_table or None,
                ref_id=ref_id or None,
                operator_id=operator_id or None,
                note=note or (f"充值{amount}分,赠送{gift}分" if gift else f"充值{amount}分"),
                ts=datetime.now(timezone.utc),
            )
            s.add(txn)
            if owns_session:
                s.commit()

            log.info(
                f"会员充值: member={member_id} +{amount}(实付)+{gift}(赠送) "
                f"balance {old_balance}->{m.balance}"
            )
            return {
                "txn_id": txn.id,
                "amount": amount,
                "gift": gift,
                "total": total,
                "balance": m.balance,
            }
        finally:
            if owns_session:
                s.close()

    def consume(
        self,
        member_id: str,
        amount: int,
        ref_table: str,
        ref_id: str,
        note: str = "",
    ) -> dict:
        """余额扣减 — CAS 原子操作防止并发双花"""
        if amount <= 0:
            raise WalletError("扣减金额必须为正数")

        owns_session = self._owns_session()
        s = self._get_session()
        try:
            from sqlalchemy import text

            # CAS 原子扣减：WHERE balance >= :amt 保证不会超额扣减
            result = s.execute(
                text(
                    "UPDATE members SET balance = balance - :amt "
                    "WHERE id = :mid AND merchant_id = :mcht AND balance >= :amt"
                ),
                {"amt": amount, "mid": member_id, "mcht": self.merchant_id},
            )
            if result.rowcount == 0:
                # 查一下是余额不足还是会员不存在
                m = (
                    s.query(MemberModel)
                    .filter_by(id=member_id, merchant_id=self.merchant_id)
                    .first()
                )
                if not m:
                    raise WalletError("会员不存在")
                raise WalletError(f"余额不足: 当前{m.balance}分, 需要{amount}分")

            # 读回最新余额
            new_balance = s.execute(
                text("SELECT balance FROM members WHERE id = :mid"),
                {"mid": member_id},
            ).fetchone()[0]

            txn = MemberWalletTxn(
                id=str(uuid.uuid4()),
                member_id=member_id,
                type="consume",
                amount=-amount,
                balance_after=new_balance,
                ref_table=ref_table or None,
                ref_id=ref_id or None,
                note=note or f"消费{amount}分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn)
            if owns_session:
                s.commit()

            log.info(f"会员消费: member={member_id} -{amount} balance={new_balance}")
            return {
                "txn_id": txn.id,
                "amount": -amount,
                "balance": new_balance,
            }
        finally:
            if owns_session:
                s.close()

    def refund(
        self,
        member_id: str,
        amount: int,
        ref_table: str,
        ref_id: str,
    ) -> dict:
        """退款返还"""
        if amount <= 0:
            raise WalletError("退款金额必须为正数")

        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise WalletError("会员不存在")

            m.balance += amount

            txn = MemberWalletTxn(
                id=str(uuid.uuid4()),
                member_id=member_id,
                type="refund",
                amount=amount,
                balance_after=m.balance,
                ref_table=ref_table or None,
                ref_id=ref_id or None,
                note=f"退款返还{amount}分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn)
            s.commit()

            log.info(f"退款返还: member={member_id} +{amount} balance={m.balance}")
            return {
                "txn_id": txn.id,
                "amount": amount,
                "balance": m.balance,
            }

    def get_balance(self, member_id: str) -> int:
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise WalletError("会员不存在")
            return m.balance

    def list_txns(self, member_id: str, limit: int = 50) -> list[dict]:
        with session_factory() as s:
            txns = (
                s.query(MemberWalletTxn)
                .filter_by(member_id=member_id)
                .order_by(MemberWalletTxn.ts.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": t.id,
                    "type": t.type,
                    "amount": t.amount,
                    "balance_after": t.balance_after,
                    "ref_table": t.ref_table,
                    "ref_id": t.ref_id,
                    "operator_id": t.operator_id,
                    "note": t.note,
                    "ts": t.ts.isoformat() if t.ts else "",
                }
                for t in txns
            ]

    def transfer(
        self, from_id: str, to_id: str, amount: int, operator_id: str = ""
    ) -> dict:
        """会员间转账"""
        if amount <= 0:
            raise WalletError("转账金额必须为正数")
        if from_id == to_id:
            raise WalletError("不能向自己转账")

        with session_factory() as s:
            from_m = (
                s.query(MemberModel)
                .filter_by(id=from_id, merchant_id=self.merchant_id)
                .first()
            )
            if not from_m:
                raise WalletError("转出会员不存在")
            to_m = (
                s.query(MemberModel)
                .filter_by(id=to_id, merchant_id=self.merchant_id)
                .first()
            )
            if not to_m:
                raise WalletError("转入会员不存在")

            if from_m.balance < amount:
                raise WalletError(
                    f"余额不足: 当前{from_m.balance}分, 需要{amount}分"
                )

            from_m.balance -= amount
            to_m.balance += amount

            txn_out = MemberWalletTxn(
                id=str(uuid.uuid4()),
                member_id=from_id,
                type="consume",
                amount=-amount,
                balance_after=from_m.balance,
                ref_table="member",
                ref_id=to_id,
                operator_id=operator_id or None,
                note=f"转账给会员{to_id[:8]}: -{amount}分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn_out)

            txn_in = MemberWalletTxn(
                id=str(uuid.uuid4()),
                member_id=to_id,
                type="deposit",
                amount=amount,
                balance_after=to_m.balance,
                ref_table="member",
                ref_id=from_id,
                operator_id=operator_id or None,
                note=f"收到会员{from_id[:8]}转账: +{amount}分",
                ts=datetime.now(timezone.utc),
            )
            s.add(txn_in)
            s.commit()

            log.info(f"会员转账: {from_id} -> {to_id} 金额={amount}")
            return {
                "from_balance": from_m.balance,
                "to_balance": to_m.balance,
                "amount": amount,
            }

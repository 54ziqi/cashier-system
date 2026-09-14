"""应用层：会员服务"""

from __future__ import annotations

import logging
import uuid

from app.infra.db.engine import session_factory
from app.infra.db.models import Member as MemberModel

log = logging.getLogger(__name__)


class MemberService:
    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def list_members(self, page: int = 1, page_size: int = 50) -> dict:
        with session_factory() as s:
            total = s.query(MemberModel).filter_by(merchant_id=self.merchant_id).count()
            items = (
                s.query(MemberModel)
                .filter_by(merchant_id=self.merchant_id)
                .order_by(MemberModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._to_dict(m) for m in items],
            }

    def get_member(self, member_id: str) -> dict | None:
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            return self._to_dict(m) if m else None

    def find_by_phone(self, phone: str) -> dict | None:
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(merchant_id=self.merchant_id, phone=phone)
                .first()
            )
            return self._to_dict(m) if m else None

    def create_member(self, data: dict) -> dict:
        with session_factory() as s:
            member = MemberModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                card_no=f"M{uuid.uuid4().hex[:10].upper()}",
                name=data.get("name", ""),
                phone=data.get("phone", ""),
                balance=0,
                points=0,
                level="normal",
            )
            s.add(member)
            s.commit()
            log.info(f"Member created: {member.name} ({member.phone})")
            return self._to_dict(member)

    def recharge(self, member_id: str, amount_yuan: float) -> dict:
        """充值：传入元，内部转分"""
        amount_cents = int(round(amount_yuan * 100))
        if amount_cents <= 0:
            raise ValueError("Recharge amount must be positive")
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise ValueError("Member not found")
            m.balance += amount_cents
            s.commit()
            log.info(
                f"Member {m.name} recharged: +{amount_cents} cents (new balance: {m.balance})"
            )
            return self._to_dict(m)

    def deduct_balance(self, member_id: str, amount_cents: int) -> dict:
        with session_factory() as s:
            m = (
                s.query(MemberModel)
                .filter_by(id=member_id, merchant_id=self.merchant_id)
                .first()
            )
            if not m:
                raise ValueError("Member not found")
            if m.balance < amount_cents:
                raise ValueError(f"Insufficient balance: {m.balance} < {amount_cents}")
            m.balance -= amount_cents
            s.commit()
            return self._to_dict(m)

    def _to_dict(self, m) -> dict:
        if not m:
            return {}
        return {
            "id": m.id,
            "merchant_id": m.merchant_id,
            "card_no": m.card_no,
            "name": m.name,
            "phone": m.phone,
            "balance": m.balance,
            "balance_yuan": round(m.balance / 100, 2),
            "points": m.points,
            "level": m.level,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }

    def seed_demo_members(self) -> int:
        """写入示例会员"""
        demo = [
            ("10001", "张三", "13800001234", 25850, 1280, "gold"),
            ("10002", "李四", "13900005678", 5200, 320, "silver"),
            ("10003", "王五", "13700009012", 0, 80, "normal"),
        ]
        with session_factory() as s:
            existing = (
                s.query(MemberModel).filter_by(merchant_id=self.merchant_id).count()
            )
            if existing > 0:
                return 0
            for card, name, phone, bal, pts, lvl in demo:
                m = MemberModel(
                    id=f"demo_m{card}",
                    merchant_id=self.merchant_id,
                    card_no=card,
                    name=name,
                    phone=phone,
                    balance=bal,
                    points=pts,
                    level=lvl,
                )
                s.add(m)
            s.commit()
            log.info(f"Seeded {len(demo)} demo members")
            return len(demo)

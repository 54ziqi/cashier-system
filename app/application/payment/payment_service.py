"""应用层：支付服务"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

from app.infra.db.models import Order as OrderModel, Payment as PaymentModel, Member as MemberModel
from app.infra.db.engine import session_factory

log = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


class PaymentMethod:
    CASH = "cash"
    MEMBER_BALANCE = "member_balance"
    WECHAT = "wechat"
    ALIPAY = "alipay"


class PaymentService:
    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def process_cash_payment(self, order_id: str, amount: int) -> dict:
        """现金支付：验证金额并计算找零"""
        with session_factory() as s:
            order = s.query(OrderModel).filter_by(id=order_id).first()
            if not order:
                raise PaymentError("Order not found")
            if order.status != "pending":
                raise PaymentError(f"Cannot pay order in {order.status} status")
            if amount < order.final_amount:
                raise PaymentError(f"Insufficient payment: {amount} < {order.final_amount}")

            change = amount - order.final_amount

            # Record payment
            payment = PaymentModel(
                id=str(uuid.uuid4()),
                order_id=order_id,
                method=PaymentMethod.CASH,
                amount=amount,
                status="success",
                paid_at=datetime.now(timezone.utc),
            )
            s.add(payment)

            # Update order
            order.status = "paid"
            order.paid_amount = amount
            order.change_amount = change

            # Auto complete
            order.status = "completed"

            s.commit()
            log.info(f"Cash payment: order={order.order_no}, amount={amount}, change={change}")

            return {
                "order_id": order_id,
                "order_no": order.order_no,
                "amount": amount,
                "change": change,
                "status": "completed",
            }

    def process_balance_payment(self, order_id: str) -> dict:
        """会员余额支付"""
        with session_factory() as s:
            order = s.query(OrderModel).filter_by(id=order_id).first()
            if not order:
                raise PaymentError("Order not found")
            if not order.member_id:
                raise PaymentError("Order has no member")
            if order.status != "pending":
                raise PaymentError(f"Cannot pay order in {order.status} status")

            member = s.query(MemberModel).filter_by(id=order.member_id).first()
            if not member:
                raise PaymentError("Member not found")
            if member.balance < order.final_amount:
                raise PaymentError(f"Insufficient balance: {member.balance} < {order.final_amount}")

            # Deduct balance
            member.balance -= order.final_amount
            # Add points (1 yuan = 1 point)
            points_earned = order.final_amount // 100
            if points_earned > 0:
                member.points += points_earned

            # Record payment
            payment = PaymentModel(
                id=str(uuid.uuid4()),
                order_id=order_id,
                method=PaymentMethod.MEMBER_BALANCE,
                amount=order.final_amount,
                status="success",
                paid_at=datetime.now(timezone.utc),
            )
            s.add(payment)

            # Update order
            order.status = "completed"
            order.paid_amount = order.final_amount
            order.change_amount = 0

            s.commit()
            log.info(f"Balance payment: order={order.order_no}, member={member.name}, amount={order.final_amount}")

            return {
                "order_id": order_id,
                "order_no": order.order_no,
                "amount": order.final_amount,
                "change": 0,
                "status": "completed",
                "member_balance": member.balance,
                "points_earned": points_earned,
            }

    def get_payments(self, order_id: str) -> list[dict]:
        with session_factory() as s:
            payments = s.query(PaymentModel).filter_by(order_id=order_id).all()
            return [{
                "id": p.id,
                "method": p.method,
                "amount": p.amount,
                "status": p.status,
                "paid_at": p.paid_at.isoformat() if p.paid_at else "",
            } for p in payments]

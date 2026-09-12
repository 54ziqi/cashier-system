"""应用层：结账服务 - 编排订单创建与支付"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

def _utcnow():
    return datetime.now(timezone.utc)
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.sales.order import Order, OrderItemVO
from app.infra.db.models import (
    Order as OrderModel, OrderItem as OrderItemModel,
    Product as ProductModel, Payment as PaymentModel,
    Member as MemberModel, AuditLog as AuditLogModel,
)
from app.infra.db.engine import session_factory

log = logging.getLogger(__name__)


class CheckoutError(Exception):
    pass


class CheckoutService:
    def __init__(self, sid: str = "local"):
        self.merchant_id = sid

    # ── public API (auto-commit) ────────────────────────────────

    def create_order(self, items: list[dict], cashier_id: str = "",
                     member_id: str = "", idempotency_key: str = "") -> Order:
        """从购物车项创建订单（独立事务）"""
        with session_factory() as s:
            try:
                order = self._do_create_order(s, items, cashier_id, member_id, idempotency_key)
                s.commit()
                return order
            except Exception:
                s.rollback()
                raise

    def checkout(self, items: list[dict], pay_method: str, cashier_id: str,
                 member_id: str = "", cash_amount: int = 0,
                 idempotency_key: str = "") -> dict:
        """
        原子结账：创建订单 + 扣减库存 + 支付 + 记账 在同一事务中。
        支付失败时整个事务回滚（库存自动恢复）。
        """
        with session_factory() as s:
            try:
                order = self._do_create_order(s, items, cashier_id, member_id, idempotency_key)
                payment = self._do_pay(s, order, pay_method, member_id, cash_amount)
                s.commit()
                log.info(f"Checkout OK: {order.order_no} pay={pay_method}")
                return {
                    "order": order,
                    "payment": payment,
                }
            except Exception:
                s.rollback()
                raise

    # ── internal ( caller controls txn ) ─────────────────────────

    def _do_create_order(self, s: Session, items: list[dict], cashier_id: str,
                         member_id: str, idempotency_key: str) -> Order:
        """在已给定的 Session 中创建订单并扣减库存"""

        # 幂等键：DB UniqueConstraint 兜底并发
        if idempotency_key:
            existing = s.query(OrderModel).filter_by(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                raise CheckoutError("Duplicate order (idempotency key already used)")

        order_items = []
        for item in items:
            product = s.query(ProductModel).filter_by(
                id=item["product_id"],
                merchant_id=self.merchant_id,
                status="active"
            ).first()
            if not product:
                raise CheckoutError(f"Product not found: {item['product_id']}")

            vo = OrderItemVO(
                product_id=product.id,
                product_name=product.name,
                barcode=product.barcode or "",
                unit_price=product.price,
                quantity=item.get("quantity", 1),
                weight=item.get("weight", 0),
                discount=item.get("discount", 0),
            )
            order_items.append(vo)

        # Build domain aggregate
        order = Order(
            merchant_id=self.merchant_id,
            cashier_id=cashier_id,
            member_id=member_id,
            idempotency_key=idempotency_key or "",
            items=order_items,
        )

        # Persist order
        order_model = OrderModel(
            id=order.id,
            order_no=order.order_no,
            merchant_id=order.merchant_id,
            cashier_id=order.cashier_id,
            member_id=order.member_id,
            idempotency_key=order.idempotency_key or None,
            status=order.status.value,
            total_amount=order.total_amount,
            discount_amount=order.discount_amount,
            final_amount=order.final_amount,
        )
        s.add(order_model)

        for vo in order.items:
            item_model = OrderItemModel(
                id=f"{order.id}_{vo.product_id}",
                order_id=order.id,
                product_id=vo.product_id,
                product_name=vo.product_name,
                barcode=vo.barcode,
                unit_price=vo.unit_price,
                quantity=vo.quantity,
                weight=vo.weight,
                subtotal=vo.subtotal,
                discount=vo.discount,
            )
            s.add(item_model)

            # 原子扣减库存：WHERE stock >= qty → rowcount=0 即超卖
            result = s.execute(
                text("UPDATE products SET stock = stock - :qty, updated_at = :now "
                     "WHERE id = :pid AND merchant_id = :mid AND stock >= :qty"),
                {"qty": vo.quantity, "now": _utcnow().isoformat(),
                 "pid": vo.product_id, "mid": self.merchant_id},
            )
            if result.rowcount == 0:
                raise CheckoutError(f"库存不足: {vo.product_name} (id={vo.product_id})")

        # 审计日志
        s.add(AuditLogModel(
            id=str(uuid.uuid4()),
            actor_type="user",
            actor_id=cashier_id,
            action="order.create",
            resource_type="order",
            resource_id=order.id,
            before_json="",
            after_json=f'{{"total": {order.final_amount}}}',
        ))

        return order

    def _do_pay(self, s: Session, order: Order, pay_method: str,
                member_id: str, cash_amount: int) -> dict:
        """在已给定的 Session 中处理支付"""

        order_m = s.query(OrderModel).filter_by(id=order.id).first()
        if not order_m:
            raise CheckoutError("Order not found in DB")

        if pay_method == "cash":
            return self._pay_cash(s, order_m, order, cash_amount)
        elif pay_method == "member_balance":
            return self._pay_balance(s, order_m, order)
        else:
            raise CheckoutError(f"支付方式 {pay_method} 尚未接入")

    def _pay_cash(self, s: Session, order_m: OrderModel, order: Order, amount: int) -> dict:
        if amount < order.final_amount:
            raise CheckoutError(f"现金不足: {amount} < {order.final_amount}")

        change = amount - order.final_amount

        payment = PaymentModel(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method="cash",
            amount=amount,
            status="success",
            paid_at=_utcnow(),
        )
        s.add(payment)

        # 通过领域状态机流转
        order.pay(amount)
        order.complete()
        order_m.status = order.status.value
        order_m.paid_amount = amount
        order_m.change_amount = change

        return {
            "order_id": order.id,
            "order_no": order.order_no,
            "amount": amount,
            "change": change,
            "status": "completed",
        }

    def _pay_balance(self, s: Session, order_m: OrderModel, order: Order) -> dict:
        if not order.member_id:
            raise CheckoutError("订单未关联会员")

        # 原子扣减余额：WHERE balance >= amount
        result = s.execute(
            text("UPDATE members SET balance = balance - :amt "
                 "WHERE id = :mid AND balance >= :amt"),
            {"amt": order.final_amount, "mid": order.member_id},
        )
        if result.rowcount == 0:
            raise CheckoutError("会员余额不足")

        # 加积分 (1元 = 1积分)
        points_earned = order.final_amount // 100
        if points_earned > 0:
            s.execute(
                text("UPDATE members SET points = points + :pts WHERE id = :mid"),
                {"pts": points_earned, "mid": order.member_id},
            )

        payment = PaymentModel(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method="member_balance",
            amount=order.final_amount,
            status="success",
            paid_at=_utcnow(),
        )
        s.add(payment)

        order.pay(order.final_amount)
        order.complete()
        order_m.status = order.status.value
        order_m.paid_amount = order.final_amount
        order_m.change_amount = 0

        # 读取最新余额
        member_m = s.query(MemberModel).filter_by(id=order.member_id).first()

        return {
            "order_id": order.id,
            "order_no": order.order_no,
            "amount": order.final_amount,
            "change": 0,
            "status": "completed",
            "member_balance": member_m.balance if member_m else 0,
            "points_earned": points_earned,
        }

    # ── queries ──────────────────────────────────────────────────

    def get_order(self, order_id: str) -> Optional[dict]:
        with session_factory() as s:
            order = s.query(OrderModel).filter_by(id=order_id).first()
            if not order:
                return None
            return {
                "id": order.id,
                "order_no": order.order_no,
                "status": order.status,
                "total_amount": order.total_amount,
                "discount_amount": order.discount_amount,
                "final_amount": order.final_amount,
                "paid_amount": order.paid_amount,
                "change_amount": order.change_amount,
                "items": [{
                    "product_name": i.product_name,
                    "unit_price": i.unit_price,
                    "quantity": i.quantity,
                    "subtotal": i.subtotal,
                } for i in order.items],
                "payments": [{
                    "method": p.method,
                    "amount": p.amount,
                    "status": p.status,
                } for p in order.payments],
                "created_at": order.created_at.isoformat() if order.created_at else "",
            }

    def list_orders(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with session_factory() as s:
            orders = s.query(OrderModel).filter_by(
                merchant_id=self.merchant_id
            ).order_by(OrderModel.created_at.desc()).limit(limit).offset(offset).all()
            return [{
                "id": o.id,
                "order_no": o.order_no,
                "status": o.status,
                "final_amount": o.final_amount,
                "created_at": o.created_at.isoformat() if o.created_at else "",
            } for o in orders]

    def refund_order(self, order_id: str) -> None:
        """原子退款：CAS 状态转换防止并发双退"""
        with session_factory() as s:
            # Step 1: CAS 原子状态转换，仅当状态为 paid/completed 才更新为 refunding
            result = s.execute(
                text("UPDATE orders SET status = 'refunding' WHERE id = :oid AND status IN ('paid', 'completed')"),
                {"oid": order_id},
            )
            if result.rowcount == 0:
                # 二次查询以给出准确错误
                cur = s.execute(text("SELECT status FROM orders WHERE id = :oid"), {"oid": order_id}).fetchone()
                if cur is None:
                    raise CheckoutError("Order not found")
                raise CheckoutError(f"Cannot refund order in {cur[0]} status")
            s.flush()

            # Step 2: 恢复库存
            items = s.execute(
                text("SELECT product_id, quantity FROM order_items WHERE order_id = :oid"),
                {"oid": order_id},
            ).fetchall()
            for item in items:
                s.execute(
                    text("UPDATE products SET stock = stock + :qty, updated_at = :now WHERE id = :pid"),
                    {"qty": item.quantity, "pid": item.product_id, "now": _utcnow().isoformat()},
                )

            # Step 3: 余额退款
            payments = s.execute(
                text("SELECT method, amount FROM payments WHERE order_id = :oid AND status = 'success'"),
                {"oid": order_id},
            ).fetchall()
            balance_paid = sum(p.amount for p in payments if p.method == "member_balance")

            if balance_paid > 0:
                member = s.execute(
                    text("SELECT member_id FROM orders WHERE id = :oid"), {"oid": order_id}
                ).fetchone()
                if member and member.member_id:
                    s.execute(
                        text("UPDATE members SET balance = balance + :amt WHERE id = :mid"),
                        {"amt": balance_paid, "mid": member.member_id},
                    )
                    log.info(f"退款返还余额: member={member.member_id} amount={balance_paid}")

            # Step 4: 状态改为 refunded
            s.execute(text("UPDATE orders SET status = 'refunded' WHERE id = :oid"), {"oid": order_id})
            s.commit()

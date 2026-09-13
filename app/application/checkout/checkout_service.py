"""应用层：结账服务 - 编排订单创建与支付"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)


from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.sales.order import Order, OrderItemVO
from app.infra.db.engine import session_factory
from app.infra.db.models import (
    AuditLog as AuditLogModel,
)
from app.infra.db.models import (
    Member as MemberModel,
)
from app.infra.db.models import (
    Order as OrderModel,
)
from app.infra.db.models import (
    OrderItem as OrderItemModel,
)
from app.infra.db.models import (
    Payment as PaymentModel,
)
from app.infra.db.models import (
    Product as ProductModel,
)

log = logging.getLogger(__name__)


class CheckoutError(Exception):
    pass


class CheckoutService:
    def __init__(self, sid: str = "local"):
        self.merchant_id = sid

    # ── public API (auto-commit) ────────────────────────────────

    def create_order(
        self,
        items: list[dict],
        cashier_id: str = "",
        member_id: str = "",
        idempotency_key: str = "",
        table_id: str = "",
        table_name: str = "",
        spec_text: str = "",
    ) -> Order:
        """从购物车项创建订单（独立事务）"""
        with session_factory() as s:
            try:
                order = self._do_create_order(
                    s, items, cashier_id, member_id, idempotency_key,
                    table_id=table_id, table_name=table_name, spec_text=spec_text,
                )
                s.commit()
                return order
            except Exception:
                s.rollback()
                raise

    def checkout(
        self,
        items: list[dict],
        pay_method: str,
        cashier_id: str,
        member_id: str = "",
        cash_amount: int = 0,
        idempotency_key: str = "",
        table_id: str = "",
        table_name: str = "",
        spec_text: str = "",
        coupon_code: str = "",
    ) -> dict:
        """
        原子结账：创建订单 + 扣减库存 + 支付 + 记账 在同一事务中。
        支付失败时整个事务回滚（库存自动恢复）。
        M3: 支持优惠券抵扣。
        M4/M5: 结账成功后消耗原料(KDS)。
        """
        order_id = ""
        with session_factory() as s:
            try:
                order = self._do_create_order(
                    s, items, cashier_id, member_id, idempotency_key,
                    table_id=table_id, table_name=table_name, spec_text=spec_text,
                    coupon_code=coupon_code,
                )
                payment = self._do_pay(s, order, pay_method, member_id, cash_amount)
                # M4: BOM 原料消耗（在同一 Session 事务中）
                self._consume_materials(s, order)
                s.commit()
                log.info(f"Checkout OK: {order.order_no} pay={pay_method}")
                order_id = order.id
                result = {
                    "order": order,
                    "payment": payment,
                }
            except Exception:
                s.rollback()
                raise

        # M5: 结账成功后创建 KDS 制作单（session 已关闭, 独立事务）
        if order_id:
            try:
                from app.application.kds.kds_service import KdsService
                KdsService(merchant_id=self.merchant_id).create_tickets(order_id)
            except Exception as e:
                log.warning(f"KDS 制作单创建失败（不影响结账）: {e}")

        return result

    @staticmethod
    def _consume_materials(s: Session, order) -> None:
        """在生产 Session 中按 BOM 消耗原料"""
        try:
            from app.application.inventory.production_service import ProductionService
            svc = ProductionService(merchant_id=getattr(order, "merchant_id", "local"))
            svc.consume_for_order(order.id, s=s)
        except Exception as e:
            log.warning(f"BOM 原料消耗失败（不影响交易）: {e}")

    # ── internal ( caller controls txn ) ─────────────────────────

    def _do_create_order(
        self,
        s: Session,
        items: list[dict],
        cashier_id: str,
        member_id: str,
        idempotency_key: str,
        table_id: str = "",
        table_name: str = "",
        spec_text: str = "",
        coupon_code: str = "",
    ) -> Order:
        """在已给定的 Session 中创建订单并扣减库存"""

        # 幂等键：DB UniqueConstraint 兜底并发
        if idempotency_key:
            existing = (
                s.query(OrderModel).filter_by(idempotency_key=idempotency_key).first()
            )
            if existing:
                raise CheckoutError("Duplicate order (idempotency key already used)")

        order_items = []
        for item in items:
            product = (
                s.query(ProductModel)
                .filter_by(
                    id=item["product_id"], merchant_id=self.merchant_id, status="active"
                )
                .first()
            )
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

        # M1 桌台/备注
        if table_id:
            order.table_id = table_id
        if table_name:
            order.table_name = table_name
        if spec_text:
            order.spec_text = spec_text

        # M3 优惠券抵扣
        if coupon_code:
            self._apply_coupon(s, order, coupon_code)

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
            table_id=table_id or None,
            table_name=table_name or None,
            spec_text=spec_text or None,
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
                text(
                    "UPDATE products SET stock = stock - :qty, updated_at = :now "
                    "WHERE id = :pid AND merchant_id = :mid AND stock >= :qty"
                ),
                {
                    "qty": vo.quantity,
                    "now": _utcnow().isoformat(),
                    "pid": vo.product_id,
                    "mid": self.merchant_id,
                },
            )
            if result.rowcount == 0:
                raise CheckoutError(f"库存不足: {vo.product_name} (id={vo.product_id})")

        # 审计日志
        s.add(
            AuditLogModel(
                id=str(uuid.uuid4()),
                actor_type="user",
                actor_id=cashier_id,
                action="order.create",
                resource_type="order",
                resource_id=order.id,
                before_json="",
                after_json=f'{{"total": {order.final_amount}}}',
            )
        )

        return order

    def _do_pay(
        self,
        s: Session,
        order: Order,
        pay_method: str,
        member_id: str,
        cash_amount: int,
    ) -> dict:
        """在已给定的 Session 中处理支付"""

        order_m = s.query(OrderModel).filter_by(id=order.id).first()
        if not order_m:
            raise CheckoutError("Order not found in DB")

        if pay_method == "cash":
            return self._pay_cash(s, order_m, order, cash_amount, member_id)
        elif pay_method == "member_balance":
            return self._pay_balance(s, order_m, order)
        else:
            raise CheckoutError(f"支付方式 {pay_method} 尚未接入")

    def _pay_cash(
        self, s: Session, order_m: OrderModel, order: Order, amount: int, member_id: str = ""
    ) -> dict:
        if amount < order.final_amount:
            raise CheckoutError(f"现金不足: {amount} < {order.final_amount}")

        change = amount - order.final_amount

        # M2: 积分赚取 (现金消费也给会员积分)
        points_earned = 0
        if member_id:
            points_earned = order.final_amount // 100
            if points_earned > 0:
                s.execute(
                    text("UPDATE members SET points = points + :pts WHERE id = :mid"),
                    {"pts": points_earned, "mid": member_id},
                )

        payment = PaymentModel(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method="cash",
            amount=amount,
            status="success",
            paid_at=_utcnow(),
        )
        s.add(payment)

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
            "points_earned": points_earned,
        }

    def _pay_balance(self, s: Session, order_m: OrderModel, order: Order) -> dict:
        if not order.member_id:
            raise CheckoutError("订单未关联会员")

        # 原子扣减余额：WHERE balance >= amount
        result = s.execute(
            text(
                "UPDATE members SET balance = balance - :amt "
                "WHERE id = :mid AND balance >= :amt"
            ),
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

    def get_order(self, order_id: str) -> dict | None:
        with session_factory() as s:
            order = s.query(OrderModel).filter_by(id=order_id).first()
            if not order:
                return None
            return {
                "id": order.id,
                "order_no": order.order_no,
                "merchant_id": order.merchant_id,
                "status": order.status,
                "total_amount": order.total_amount,
                "discount_amount": order.discount_amount,
                "final_amount": order.final_amount,
                "paid_amount": order.paid_amount,
                "change_amount": order.change_amount,
                "table_id": order.table_id,
                "table_name": order.table_name,
                "spec_text": order.spec_text,
                "items": [
                    {
                        "product_name": i.product_name,
                        "unit_price": i.unit_price,
                        "quantity": i.quantity,
                        "subtotal": i.subtotal,
                    }
                    for i in order.items
                ],
                "payments": [
                    {
                        "method": p.method,
                        "amount": p.amount,
                        "status": p.status,
                    }
                    for p in order.payments
                ],
                "created_at": order.created_at.isoformat() if order.created_at else "",
            }

    def list_orders(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with session_factory() as s:
            orders = (
                s.query(OrderModel)
                .filter_by(merchant_id=self.merchant_id)
                .order_by(OrderModel.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [
                {
                    "id": o.id,
                    "order_no": o.order_no,
                    "merchant_id": o.merchant_id,
                    "status": o.status,
                    "final_amount": o.final_amount,
                    "created_at": o.created_at.isoformat() if o.created_at else "",
                }
                for o in orders
            ]

    def refund_order(self, order_id: str) -> None:
        """
        原子退款：CAS 状态转换防止并发双退。
        P1-W2: CAS + 库存恢复 + 余额退款 三段包进同一 SAVEPOINT,
        任意失败 → rollback 到 savepoint, 订单状态恢复为 paid, 重新 raise。
        """
        with session_factory() as s:
            # Step 1: CAS 原子状态转换
            result = s.execute(
                text(
                    "UPDATE orders SET status = 'refunding' WHERE id = :oid AND status IN ('paid', 'completed')"
                ),
                {"oid": order_id},
            )
            if result.rowcount == 0:
                cur = s.execute(
                    text("SELECT status FROM orders WHERE id = :oid"), {"oid": order_id}
                ).fetchone()
                if cur is None:
                    raise CheckoutError("Order not found")
                raise CheckoutError(f"Cannot refund order in {cur[0]} status")

            # 开始 SAVEPOINT: 后续库存恢复/余额退款 任何失败都回滚到这里
            s.execute(text("SAVEPOINT refund_sp"))
            try:
                # Step 2: 恢复库存
                items = s.execute(
                    text(
                        "SELECT product_id, quantity FROM order_items WHERE order_id = :oid"
                    ),
                    {"oid": order_id},
                ).fetchall()
                for item in items:
                    s.execute(
                        text(
                            "UPDATE products SET stock = stock + :qty, updated_at = :now WHERE id = :pid"
                        ),
                        {
                            "qty": item.quantity,
                            "pid": item.product_id,
                            "now": _utcnow().isoformat(),
                        },
                    )

                # Step 3: 余额退款
                payments = s.execute(
                    text(
                        "SELECT method, amount FROM payments WHERE order_id = :oid AND status = 'success'"
                    ),
                    {"oid": order_id},
                ).fetchall()
                balance_paid = sum(
                    p.amount for p in payments if p.method == "member_balance"
                )

                if balance_paid > 0:
                    member = s.execute(
                        text("SELECT member_id FROM orders WHERE id = :oid"),
                        {"oid": order_id},
                    ).fetchone()
                    if member and member.member_id:
                        s.execute(
                            text(
                                "UPDATE members SET balance = balance + :amt WHERE id = :mid"
                            ),
                            {"amt": balance_paid, "mid": member.member_id},
                        )
                        log.info(
                            f"退款返还余额: member={member.member_id} amount={balance_paid}"
                        )

                # Step 3.5: 扣回积分（退还本次订单获得的积分）
                earned_rows = s.execute(
                    text(
                        "SELECT points FROM member_points_txns "
                        "WHERE ref_table = 'orders' AND ref_id = :oid AND type = 'earn'"
                    ),
                    {"oid": order_id},
                ).fetchall()
                total_earned = sum(r.points for r in earned_rows)
                if total_earned > 0:
                    member_for_points = s.execute(
                        text("SELECT member_id FROM orders WHERE id = :oid"),
                        {"oid": order_id},
                    ).fetchone()
                    if member_for_points and member_for_points.member_id:
                        s.execute(
                            text(
                                "UPDATE members SET points = points - :pts WHERE id = :mid"
                            ),
                            {"pts": total_earned, "mid": member_for_points.member_id},
                        )
                        s.execute(
                            text(
                                "INSERT INTO member_points_txns "
                                "(id, member_id, type, points, ref_table, ref_id, note, ts) "
                                "VALUES (:id, :mid, 'refund', :pts, 'orders', :oid, :note, :now)"
                            ),
                            {
                                "id": __import__("uuid").uuid4().hex,
                                "mid": member_for_points.member_id,
                                "pts": -total_earned,
                                "oid": order_id,
                                "note": f"退款扣回{total_earned}积分",
                                "now": _utcnow().isoformat(),
                            },
                        )
                        log.info(f"退款扣回积分: member={member_for_points.member_id} points={-total_earned}")

                # Step 3.6: 退还优惠券（将已核销券状态恢复为 unused）
                used_coupon = s.execute(
                    text(
                        "SELECT id FROM coupons WHERE ref_order_id = :oid AND status = 'used'"
                    ),
                    {"oid": order_id},
                ).fetchone()
                if used_coupon:
                    s.execute(
                        text(
                            "UPDATE coupons SET status = 'unused', used_at = NULL, ref_order_id = NULL WHERE id = :cid"
                        ),
                        {"cid": used_coupon.id},
                    )
                    log.info(f"退款退券: coupon={used_coupon.id}")

                # Step 3.7: 恢复 BOM 原料库存
                try:
                    from app.application.inventory.production_service import ProductionService
                    prod_svc = ProductionService(merchant_id=self.merchant_id)
                    restored_materials = prod_svc.restore_for_refund(order_id, session=s)
                    if restored_materials:
                        log.info(f"退款归还原料: {len(restored_materials)} 项")
                except Exception as mat_e:
                    log.warning(f"BOM 原料归还失败（跳过）: {mat_e}")

                # Step 4: 状态改为 refunded
                s.execute(
                    text("UPDATE orders SET status = 'refunded' WHERE id = :oid"),
                    {"oid": order_id},
                )
            except Exception:
                # 任何一步失败 → rollback 到 savepoint, 恢复订单为 paid
                s.execute(text("ROLLBACK TO SAVEPOINT refund_sp"))
                s.execute(
                    text("UPDATE orders SET status = 'paid' WHERE id = :oid"),
                    {"oid": order_id},
                )
                s.commit()
                raise
            # 释放 savepoint
            s.execute(text("RELEASE SAVEPOINT refund_sp"))
            s.commit()

    def _apply_coupon(self, s: Session, order: Order, code: str) -> None:
        """在结账 Session 中核销优惠券并应用折扣

        支持的券类型:
        - "amount": 直减，value 单位是分
        - "percentage": 折扣率，value 单位是 % (如 80 表示八折，减 20%)
        """
        from app.application.promotion.coupon_service import CouponService

        svc = CouponService(merchant_id=self.merchant_id)

        # 用订单上下文校验最低消费（订单在创建时已经算好 total_amount）
        result = svc.validate_coupon(code, order_context={"subtotal": order.total_amount})
        if not result.get("valid"):
            raise CheckoutError(f"优惠券无效: {result.get('reason', 'unknown')}")
        if result.get("min_amount", 0) > order.total_amount:
            raise CheckoutError(
                f"消费未满{result['min_amount']}分，无法使用该优惠券"
            )

        tpl_type = result["type"]
        value = result["value"]

        if tpl_type == "amount":
            # 直减：value 单位是分，不超过订单总额
            discount = min(value, order.total_amount)
            order.apply_discount(discount)
        elif tpl_type == "percentage":
            # 折扣率：value 如 80 表示八折 → 减 (100-80)%
            discount = int(order.total_amount * (100 - value) / 100)
            if discount > 0:
                order.apply_discount(discount)
        else:
            raise CheckoutError(f"不支持的券类型: {tpl_type}")

        # 在同一个 session 中核销，参与 checkout 事务
        svc.redeem(code, order_id=order.id, session=s)

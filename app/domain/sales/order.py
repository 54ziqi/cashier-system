"""领域层：订单聚合根 + 状态机"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItemVO:
    """订单项值对象（新建订单时传入）"""

    def __init__(
        self,
        product_id: str,
        product_name: str,
        barcode: str,
        unit_price: int,
        quantity: float = 1,
        weight: float = 0,
        discount: int = 0,
    ):
        self.product_id = product_id
        self.product_name = product_name
        self.barcode = barcode
        self.unit_price = unit_price  # 分
        self.quantity = quantity
        self.weight = weight
        self.discount = discount

    @property
    def subtotal(self) -> int:
        return int(self.unit_price * self.quantity) - self.discount


class Order:
    """订单聚合根"""

    def __init__(
        self,
        merchant_id: str,
        cashier_id: str = "",
        member_id: str = "",
        idempotency_key: str = "",
        items: list[OrderItemVO] = None,
    ):
        self.id = str(uuid.uuid4())
        self.order_no = self._gen_order_no()
        self.merchant_id = merchant_id
        self.cashier_id = cashier_id
        self.member_id = member_id
        self.idempotency_key = idempotency_key or str(uuid.uuid4())
        self.items: list[OrderItemVO] = items or []
        self.status = OrderStatus.PENDING
        self.discount_amount = 0
        self.total_amount = 0
        self.final_amount = 0
        self.paid_amount = 0
        self.change_amount = 0
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.version = 0
        self._recalc()

    def _gen_order_no(self) -> str:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"ORD{ts}{self.id[:6].upper()}"

    def add_item(self, item: OrderItemVO) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot add item in {self.status} status")
        self.items.append(item)
        self._recalc()

    def apply_discount(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Discount cannot be negative")
        self.discount_amount = min(amount, self.total_amount)
        self._recalc()

    def pay(self, paid_amount: int) -> int:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot pay in {self.status} status")
        if paid_amount < self.final_amount:
            raise ValueError(
                f"Insufficient payment: {paid_amount} < {self.final_amount}"
            )
        self.paid_amount = paid_amount
        self.change_amount = max(paid_amount - self.final_amount, 0)
        self.status = OrderStatus.PAID
        self.updated_at = datetime.now(timezone.utc)
        return self.change_amount

    def complete(self) -> None:
        if self.status != OrderStatus.PAID:
            raise ValueError(f"Cannot complete in {self.status} status")
        self.status = OrderStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        if self.status not in (OrderStatus.PENDING,):
            raise ValueError(f"Cannot cancel in {self.status} status")
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)

    def refund(self) -> None:
        if self.status not in (OrderStatus.PAID, OrderStatus.COMPLETED):
            raise ValueError(f"Cannot refund in {self.status} status")
        self.status = OrderStatus.REFUNDED
        self.updated_at = datetime.now(timezone.utc)

    def _recalc(self) -> None:
        total = sum(item.subtotal for item in self.items)
        self.total_amount = max(total, 0)
        self.final_amount = max(self.total_amount - self.discount_amount, 0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_no": self.order_no,
            "status": self.status.value,
            "total_amount": self.total_amount,
            "discount_amount": self.discount_amount,
            "final_amount": self.final_amount,
            "paid_amount": self.paid_amount,
            "change_amount": self.change_amount,
            "items": [
                {
                    "product_id": i.product_id,
                    "product_name": i.product_name,
                    "unit_price": i.unit_price,
                    "quantity": i.quantity,
                    "weight": i.weight,
                    "subtotal": i.subtotal,
                }
                for i in self.items
            ],
            "created_at": self.created_at.isoformat(),
        }

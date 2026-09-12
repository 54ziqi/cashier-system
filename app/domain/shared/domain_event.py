"""Domain Event 基类"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class OrderCreated(DomainEvent):
    order_id: str = ""
    merchant_id: str = ""
    total_amount: int = 0


@dataclass(frozen=True)
class OrderPaid(DomainEvent):
    order_id: str = ""
    payment_method: str = ""
    amount: int = 0


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    order_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class StockChanged(DomainEvent):
    product_id: str = ""
    delta: float = 0
    remaining: float = 0


@dataclass(frozen=True)
class StockLow(DomainEvent):
    product_id: str = ""
    remaining: float = 0
    days_to_depletion: float = 0


@dataclass(frozen=True)
class MemberUpgraded(DomainEvent):
    member_id: str = ""
    new_level: str = ""


@dataclass(frozen=True)
class MemberBalanceChanged(DomainEvent):
    member_id: str = ""
    delta: int = 0
    new_balance: int = 0

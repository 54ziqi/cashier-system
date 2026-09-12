"""数据库模型：订单/商品/会员/支付等完整表结构"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.engine import Base


def now():
    return datetime.now(timezone.utc)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    license_type: Mapped[str] = mapped_column(String(16), default="free")
    license_expire_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    version: Mapped[int] = mapped_column(Integer, default=0)


class RevokedToken(Base):
    """已撤销 Token 的持久化存储，跨重启保持撤销状态"""
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)


class LocalCredential(Base):
    __tablename__ = "local_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[float] = mapped_column(Float, default=0.0)
    last_login: Mapped[float] = mapped_column(Float, default=0.0)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    barcode: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # 分
    cost_price: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(16), default="pcs")
    is_weighing: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str] = mapped_column(String(8), default="📦")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint("merchant_id", "barcode", name="uq_product_barcode"),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    card_no: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32), index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # 分
    points: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(16), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint("merchant_id", "phone", name="uq_member_phone"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    cashier_id: Mapped[str] = mapped_column(String(36))
    member_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    final_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)
    change_amount: Mapped[int] = mapped_column(Integer, default=0)
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    version: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # Index for list queries
        {"sqlite_autoincrement": False},
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36))
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    barcode: Mapped[str] = mapped_column(String(64))
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1)
    weight: Mapped[float] = mapped_column(Float, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0)

    order: Mapped["Order"] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    order: Mapped["Order"] = relationship(back_populates="payments")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    device_name: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="offline")
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(36))
    before_json: Mapped[str] = mapped_column(Text)
    after_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    synced_at: Mapped[datetime] = mapped_column(DateTime)

"""数据库模型：订单/商品/会员/支付等完整表结构"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.engine import Base


def now():
    return datetime.now(timezone.utc)


class Tenant(Base):
    """
    租户表：每店一行。由 License payload 写入，店名/等级/父租户 ID 受激活码保护不可本地修改。

    license_type: single | chain_parent | chain_node
    license_tier: single | chain_flagship | chain_unlimited (仅 chain_parent 填写)
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # ── 激活码锁定字段 (本地不可修改) ──
    license_store_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="未授权门店"
    )
    license_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="single"
    )  # single | chain_parent | chain_node
    license_tier: Mapped[str] = mapped_column(
        String(16), default="single"
    )  # single | chain_flagship | chain_unlimited
    parent_tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, default=None
    )
    max_stores: Mapped[int] = mapped_column(Integer, default=1)  # 母店配额
    hardware_fingerprint: Mapped[str] = mapped_column(
        String(128), nullable=True, default=None
    )

    # ── 业态模板 (本地可改) ──
    industry: Mapped[str] = mapped_column(
        String(32), nullable=False, default="fast_food",
    )  # fast_food | full_service | beverage | hotpot | bakery | retail

    # ── 经营信息 (本地可改) ──
    contact_name: Mapped[str] = mapped_column(String(64), nullable=True, default=None)
    phone: Mapped[str] = mapped_column(String(32), nullable=True, default=None)
    address: Mapped[str] = mapped_column(String(256), nullable=True, default=None)

    status: Mapped[str] = mapped_column(String(16), default="active")
    license_expire_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Merchant(Base):
    """
    兼容旧表名：POS 端代码中 Merchant 引用全部平滑迁移到 Tenant。
    本模型保留用于兼容已有 admin API 接口，实际 CRUD 落到 tenants 表。
    """

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
    """已撤销 Token 的持久化存储 (deprecated: 保留用于迁移兼容, 不再写入)"""

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
    token_version: Mapped[int] = mapped_column(Integer, default=0)


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

    # ── 行业扩展字段（JSON 形式避免 schema 频繁变更） ──
    is_combo: Mapped[int] = mapped_column(Integer, default=0)         # 是否套餐
    bom_json: Mapped[str] = mapped_column(Text, nullable=True, default=None)  # 配方 JSON
    is_86: Mapped[int] = mapped_column(Integer, default=0)             # 是否沽清
    specs_json: Mapped[str] = mapped_column(Text, nullable=True, default=None)  # 扩展属性 JSON

    __table_args__ = (
        UniqueConstraint("merchant_id", "barcode", name="uq_product_barcode"),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, default=None
    )
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

    __table_args__ = (UniqueConstraint("merchant_id", "phone", name="uq_member_phone"),)


class ProductSpecOption(Base):
    """商品选项值：每个选项的一个可选值（如中杯/大杯）"""
    __tablename__ = "product_spec_options"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    option_name: Mapped[str] = mapped_column(String(64), nullable=False)    # 杯型/温度/糖度/辣度
    value: Mapped[str] = mapped_column(String(64), nullable=False)          # 中杯/少冰/三分糖/微辣
    price_delta: Mapped[int] = mapped_column(Integer, default=0)            # 差价（分）


class ProductSpecGroup(Base):
    """商品选项组：每种选项类型定义，如"杯型"组、"糖度"组"""
    __tablename__ = "product_spec_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    required: Mapped[bool] = mapped_column(Integer, default=0)             # 是否必选
    min_select: Mapped[int] = mapped_column(Integer, default=1)
    max_select: Mapped[int] = mapped_column(Integer, default=1)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    cashier_id: Mapped[str] = mapped_column(String(36))
    member_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    final_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)
    change_amount: Mapped[int] = mapped_column(Integer, default=0)
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")
    # ── M1 扩展字段 ──
    kitchen_status: Mapped[str] = mapped_column(String(16), default="pending")
    table_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(36), nullable=True)
    course_sequence: Mapped[int] = mapped_column(Integer, default=0)
    is_merged: Mapped[int] = mapped_column(Integer, default=0)
    spec_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    queue_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_exp_discount: Mapped[int] = mapped_column(Integer, default=0)
    pot_flavor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # ── 时间戳 ──
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    version: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # Index for list queries
        {"sqlite_autoincrement": False},
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(36))
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    barcode: Mapped[str] = mapped_column(String(64))
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1)
    weight: Mapped[float] = mapped_column(Float, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    # ── M1 扩展字段 ──
    spec_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_voided_item: Mapped[int] = mapped_column(Integer, default=0)
    parent_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusLog(Base):
    """订单状态变更日志"""
    __tablename__ = "order_status_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor_type: Mapped[str] = mapped_column(String(16))  # user / system / promotion_engine
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        Index("idx_osl_order_ts", "order_id", "ts"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    order: Mapped[Order] = relationship(back_populates="payments")


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


class DiningTable(Base):
    """桌台模型"""
    __tablename__ = "dining_tables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[str] = mapped_column(String(16), default="empty")
    current_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pos_x: Mapped[int] = mapped_column(Integer, default=0)
    pos_y: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint("merchant_id", "name", name="uq_table_name"),
        Index("idx_tables_merchant_status", "merchant_id", "status"),
    )


# ── M4/M5 模型 ──


class Material(Base):
    """原料/物料"""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="g")
    cost_price: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)
    safety_stock: Mapped[float] = mapped_column(Float, default=0)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Warehouse(Base):
    """仓库"""

    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), default="main")
    address: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class WarehouseStock(Base):
    """仓库-物料库存"""

    __tablename__ = "warehouse_stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "material_id", name="uq_wh_mat"),
        Index("idx_ws_wh", "warehouse_id"),
    )


class RecipeBOM(Base):
    """菜品配方 BOM（商品 → 所需原料）"""

    __tablename__ = "recipe_boms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    wastage_pct: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(16), default="g")

    __table_args__ = (
        UniqueConstraint("product_id", "material_id", name="uq_bom"),
        Index("idx_bom_product", "product_id"),
    )


class PurchaseOrder(Base):
    """采购单"""

    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    supplier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    expected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PurchaseOrderItem(Base):
    """采购单明细项"""

    __tablename__ = "purchase_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    po_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    qty_ordered: Mapped[float] = mapped_column(Float, nullable=False)
    qty_received: Mapped[float] = mapped_column(Float, default=0)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)


class StockMovement(Base):
    """库存变动流水"""

    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, default=0)
    ref_table: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)


class PhysicalInventorySheet(Base):
    """盘点单"""

    __tablename__ = "physical_inventory_sheets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    counted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_variance: Mapped[int] = mapped_column(Integer, default=0)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PhysicalInventoryLine(Base):
    """盘点单明细行"""

    __tablename__ = "physical_inventory_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sheet_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    book_qty: Mapped[float] = mapped_column(Float, nullable=False)
    counted_qty: Mapped[float] = mapped_column(Float, nullable=False)
    variance: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)
    variance_amount: Mapped[int] = mapped_column(Integer, default=0)


class FinancialReport(Base):
    """日结财务报表快照"""

    __tablename__ = "financial_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[int] = mapped_column(Integer, default=0)
    gross_profit: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "report_type", "period_start", "period_end",
            name="uq_fin_report",
        ),
        Index("idx_finr_merchant_period", "merchant_id", "period_start"),
    )


class KdsTicket(Base):
    """厨房制作单"""

    __tablename__ = "kds_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1)
    spec_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    urgent: Mapped[int] = mapped_column(Integer, default=0)
    fire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    kds_station: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class EscPosJob(Base):
    """打印任务"""

    __tablename__ = "escpos_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(36), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error_msg: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ── M6 模型 ──

_utcnow = now


class TransferOrder(Base):
    """门店间库存调拨单"""

    __tablename__ = "transfer_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    total_qty: Mapped[float] = mapped_column(Float, default=0)
    operator_id: Mapped[str] = mapped_column(String(36), nullable=True)
    freight_cost: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(256), nullable=True)
    shipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class TransferOrderItem(Base):
    """调拨单明细行"""

    __tablename__ = "transfer_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)


class Settlement(Base):
    """集团分账结算单"""

    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    hq_amount: Mapped[int] = mapped_column(Integer, default=0)
    store_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    config_snapshot_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class PolicyReceipt(Base):
    """策略下发接收回执（POS 端记录接收状态）"""

    __tablename__ = "policy_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    push_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    conflict_detail_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ── M2/M3 模型 ──


class MemberLevel(Base):
    """规则化会员等级"""
    __tablename__ = "member_levels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    min_spend: Mapped[int] = mapped_column(Integer, default=0)
    min_points: Mapped[int] = mapped_column(Integer, default=0)
    discount_pct: Mapped[int] = mapped_column(Integer, default=0)
    benefits_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MemberLevelHistory(Base):
    """会员等级变更历史"""
    __tablename__ = "member_level_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_level: Mapped[str] = mapped_column(String(16))
    to_level: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(256), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)


class MemberWalletTxn(Base):
    """储值钱包流水"""
    __tablename__ = "member_wallet_txns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_table: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True, default=None)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)


class MemberPointsTxn(Base):
    """积分流水"""
    __tablename__ = "member_points_txns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_table: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True, default=None)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class MemberTag(Base):
    """消费标签"""
    __tablename__ = "member_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    source: Mapped[str] = mapped_column(String(16), default="auto")
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)


class PromotionRule(Base):
    """促销规则"""
    __tablename__ = "promotion_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    conditions_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    actions_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    stackable: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CouponTemplate(Base):
    """优惠券模板"""
    __tablename__ = "coupon_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    min_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_qty: Mapped[int] = mapped_column(Integer, default=0)
    issued_qty: Mapped[int] = mapped_column(Integer, default=0)
    used_qty: Mapped[int] = mapped_column(Integer, default=0)
    valid_days: Mapped[int] = mapped_column(Integer, default=30)
    applicable_products_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Coupon(Base):
    """具体优惠券实例"""
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="unused")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    ref_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)

    __table_args__ = (UniqueConstraint("code", name="uq_coupon_code"),)


class CampaignTask(Base):
    """营销活动推送任务"""
    __tablename__ = "campaign_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(String(32), nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    coupon_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

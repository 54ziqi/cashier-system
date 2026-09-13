"""
云端聚合服务数据模型

存储 POS 端推送的日结签名数据，并提供跨店聚合视图。
云端仅做只读聚合，不写任何业务 API 源数据。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DailyDigest(Base):
    """POS 推送的日结摘要（不可篡改：写入后只读，同 (merchant_id, date) 唯一）"""

    __tablename__ = "daily_digests"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    merchant_id = Column(String(36), nullable=False, index=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    gross_sales = Column(Float, default=0)
    order_count = Column(Integer, default=0)
    signature = Column(Text, nullable=False)  # RSA-SHA256 验签用
    payload_json = Column(Text, nullable=False)  # 原始 payload
    uploaded_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("merchant_id", "date", name="uq_daily_merchant_date"),
    )


class TenantRegistry(Base):
    """云端侧商户注册表（POS push 第一条数据时自动注册, 同名 store_name 锁定）"""

    __tablename__ = "tenant_registry"

    merchant_id = Column(String(36), primary_key=True)
    parent_merchant_id = Column(String(36), nullable=True, index=True)
    store_name = Column(String(128), nullable=False, default="门店")
    tier = Column(String(16), default="single")
    max_stores = Column(Integer, default=1)
    first_seen = Column(DateTime, default=_utcnow)
    last_seen = Column(DateTime, default=_utcnow)
    active = Column(Boolean, default=True)


class StoreRelation(Base):
    """连锁关系表：parent → [child_ids]"""

    __tablename__ = "store_relations"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    parent_merchant_id = Column(String(36), nullable=False, index=True)
    child_merchant_id = Column(String(36), nullable=False, index=True)
    child_store_name = Column(String(128), nullable=False, default="")
    joined_at = Column(DateTime, default=_utcnow)


class PolicyPush(Base):
    """集团策略下发推送记录（ledger）"""

    __tablename__ = "policy_pushes"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    parent_tenant_id = Column(String(36), nullable=False, index=True)
    target_tenant_id = Column(String(36), nullable=False, index=True)
    policy_type = Column(String(32), nullable=False)  # menu | prices | members | promotions
    payload_json = Column(Text, nullable=False)
    push_version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


def init_db(db_path: str = "cloud/data/cloud.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

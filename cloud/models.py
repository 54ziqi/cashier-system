"""
云端聚合服务数据模型

存储 POS 端推送的日结签名数据，并提供跨店聚合视图。
云端仅做只读聚合，不写任何业务 API 源数据。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text, Boolean, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class DailyDigest(Base):
    """POS 推送的日结摘要（不可篡改：写入后只读）"""
    __tablename__ = "daily_digests"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    merchant_id = Column(String(36), nullable=False, index=True)
    date = Column(String(10), nullable=False)          # YYYY-MM-DD
    gross_sales = Column(Float, default=0)
    order_count = Column(Integer, default=0)
    signature = Column(Text, nullable=False)            # RSA-SHA256 验签用
    payload_json = Column(Text, nullable=False)         # 原始 payload
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class TenantRegistry(Base):
    """云端侧商户注册表（POS push 第一条数据时自动注册）"""
    __tablename__ = "tenant_registry"

    merchant_id = Column(String(36), primary_key=True)
    parent_merchant_id = Column(String(36), nullable=True, index=True)
    store_name = Column(String(128), nullable=False, default="门店")
    tier = Column(String(16), default="single")
    max_stores = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)


class StoreRelation(Base):
    """连锁关系表：parent → [child_ids]"""
    __tablename__ = "store_relations"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    parent_merchant_id = Column(String(36), nullable=False, index=True)
    child_merchant_id = Column(String(36), nullable=False, index=True)
    child_store_name = Column(String(128), nullable=False, default="")
    joined_at = Column(DateTime, default=datetime.utcnow)


def init_db(db_path: str = "cloud/data/cloud.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

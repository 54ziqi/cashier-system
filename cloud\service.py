"""
云端聚合服务业务逻辑

只读聚合：写入后同 (merchant_id, date) 数据被覆盖更新 (idempotent),
store_name 第一次 ingest 后锁定不再变更。
"""

from __future__ import annotations

import json as _json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .models import DailyDigest, PolicyPush, StoreRelation, TenantRegistry


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ingest_digest(session, payload: dict, signature: str) -> DailyDigest:
    """入库一个日结摘要; 同 (merchant_id, date) 做覆盖更新 (idempotent)"""
    merchant_id = payload["merchant_id"]
    date = payload["date"]

    d = DailyDigest(
        merchant_id=merchant_id,
        date=date,
        gross_sales=payload.get("gross_sales", 0),
        order_count=payload.get("order_count", 0),
        signature=signature,
        payload_json=__import__("json").dumps(payload),
    )
    session.add(d)

    # 唯一约束冲突 → 覆盖原记录的数值字段, 模拟 UPSERT
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        # 查找已有记录原地覆盖
        d_existing = (
            session.query(DailyDigest)
            .filter_by(merchant_id=merchant_id, date=date)
            .first()
        )
        if d_existing is not None:
            d_existing.gross_sales = payload.get("gross_sales", d_existing.gross_sales)
            d_existing.order_count = payload.get("order_count", d_existing.order_count)
            d_existing.signature = signature
            d_existing.payload_json = __import__("json").dumps(payload)
            session.commit()
            d = d_existing
        else:
            # 未知情况，重新 raise
            raise

    # 自动注册商户: 首次注册时锁定 store_name, 后续不再更新该字段
    existing_reg = session.query(TenantRegistry).get(merchant_id)
    if not existing_reg:
        reg = TenantRegistry(
            merchant_id=merchant_id,
            parent_merchant_id=payload.get("parent_merchant_id") or None,
            store_name=payload.get("store_name", "门店"),
            max_stores=payload.get("max_stores", 1),
            tier="chain_parent" if payload.get("parent_merchant_id") else "single",
        )
        session.add(reg)
    else:
        existing_reg.last_seen = _utcnow()
        # W-6: store_name 仅在首次 ingest 时写入, 后续不再更新
        # (首次已锁定, 此处不做任何更新)
    session.commit()
    return d


# ── 聚合查询 ────────────────────────────────────────────────────────


def aggregate_single(session, merchant_id: str, days: int = 7) -> dict:
    """单店聚合"""
    since = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = (
        session.query(
            DailyDigest.date,
            func.sum(DailyDigest.gross_sales).label("rev"),
            func.sum(DailyDigest.order_count).label("cnt"),
        )
        .filter(DailyDigest.merchant_id == merchant_id, DailyDigest.date >= since)
        .group_by(DailyDigest.date)
        .order_by(DailyDigest.date)
        .all()
    )
    return {
        "merchant_id": merchant_id,
        "range_days": days,
        "series": [{"date": r.date, "revenue": r.rev, "count": r.cnt} for r in rows],
    }


def aggregate_chain(session, parent_id: str, days: int = 7) -> dict:
    """跨店聚合：汇总所有子店数据"""
    children = (
        session.query(TenantRegistry)
        .filter_by(parent_merchant_id=parent_id, active=True)
        .all()
    )
    child_ids = [c.merchant_id for c in children]
    if not child_ids:
        # fallback: 从 store_relations
        rels = (
            session.query(StoreRelation).filter_by(parent_merchant_id=parent_id).all()
        )
        child_ids = [r.child_merchant_id for r in rels]

    since = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = (
        session.query(
            DailyDigest.merchant_id,
            func.sum(DailyDigest.gross_sales).label("rev"),
            func.sum(DailyDigest.order_count).label("cnt"),
        )
        .filter(
            DailyDigest.merchant_id.in_(child_ids + [parent_id]),
            DailyDigest.date >= since,
        )
        .group_by(DailyDigest.merchant_id)
        .all()
    )

    store_lookup = {c.merchant_id: c.store_name for c in children}
    store_lookup[parent_id] = "(母店)"

    by_store = []
    total_rev = 0
    total_cnt = 0
    for r in rows:
        total_rev += r.rev
        total_cnt += r.cnt
        by_store.append(
            {
                "merchant_id": r.merchant_id,
                "store_name": store_lookup.get(r.merchant_id, r.merchant_id),
                "revenue": r.rev,
                "count": r.cnt,
            }
        )
    by_store.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "parent_id": parent_id,
        "range_days": days,
        "children_count": len(child_ids) + 1,
        "total_revenue": total_rev,
        "total_orders": total_cnt,
        "ranking": by_store,
    }


def list_chain_stores(session, parent_id: str) -> list:
    """查询母店旗下所有子店"""
    children = (
        session.query(TenantRegistry)
        .filter_by(parent_merchant_id=parent_id, active=True)
        .all()
    )
    return [
        {
            "merchant_id": c.merchant_id,
            "store_name": c.store_name,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None,
        }
        for c in children
    ]


# ── M6 策略推送记录 ─────────────────────────────────────────────────


def record_policy_push(
    session,
    parent_tenant_id: str,
    target_tenant_id: str,
    policy_type: str,
    payload: dict,
) -> int:
    """记录一次策略推送并返回 push_version"""
    # 当前最大版本号 +1
    max_ver = (
        session.query(func.coalesce(func.max(PolicyPush.push_version), 0))
        .filter_by(target_tenant_id=target_tenant_id, policy_type=policy_type)
        .scalar()
        or 0
    )
    push = PolicyPush(
        id=uuid.uuid4().hex,
        parent_tenant_id=parent_tenant_id,
        target_tenant_id=target_tenant_id,
        policy_type=policy_type,
        payload_json=_json.dumps(payload, ensure_ascii=False),
        push_version=max_ver + 1,
    )
    session.add(push)
    session.commit()
    return push.push_version

"""
云端聚合服务业务逻辑

只读聚合：写入后不再修改，所有查询基于已入库的日结数据。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from .models import DailyDigest, TenantRegistry, StoreRelation


def ingest_digest(session, payload: dict, signature: str) -> DailyDigest:
    """入库一个日结摘要"""
    d = DailyDigest(
        merchant_id=payload["merchant_id"],
        date=payload["date"],
        gross_sales=payload.get("gross_sales", 0),
        order_count=payload.get("order_count", 0),
        signature=signature,
        payload_json=__import__("json").dumps(payload),
    )
    session.add(d)

    # 自动注册商户
    existing = session.query(TenantRegistry).get(payload["merchant_id"])
    if not existing:
        reg = TenantRegistry(
            merchant_id=payload["merchant_id"],
            parent_merchant_id=payload.get("parent_merchant_id") or None,
            store_name=payload.get("store_name", "门店"),
            max_stores=payload.get("max_stores", 1),
        )
        session.add(reg)
    else:
        existing.last_seen = datetime.utcnow()
        if payload.get("store_name"):
            existing.store_name = payload.get("store_name", existing.store_name)
    session.commit()
    return d


# ── 聚合查询 ────────────────────────────────────────────────────────


def aggregate_single(session, merchant_id: str, days: int = 7) -> dict:
    """单店聚合"""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
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
        rels = session.query(StoreRelation).filter_by(parent_merchant_id=parent_id).all()
        child_ids = [r.child_merchant_id for r in rels]

    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = (
        session.query(
            DailyDigest.merchant_id,
            func.sum(DailyDigest.gross_sales).label("rev"),
            func.sum(DailyDigest.order_count).label("cnt"),
        )
        .filter(DailyDigest.merchant_id.in_(child_ids + [parent_id]),
                 DailyDigest.date >= since)
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
        by_store.append({
            "merchant_id": r.merchant_id,
            "store_name": store_lookup.get(r.merchant_id, r.merchant_id),
            "revenue": r.rev,
            "count": r.cnt,
        })
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

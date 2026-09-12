"""
销售数据看板 API — 7 视图聚合数据

鉴权策略：
- 任何已登录用户可见本地看板 (/overview /today /cashier /member)
- chain_view 授权用户 (/chain/*) 额外可见门店对比、跨店分析
- single 类型用户不能访问 chain_view 路由
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func

from app.api.deps import get_current_user
from app.infra.db.engine import session_factory
from app.infra.db.models import Order, OrderItem, Member, Product, Payment

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ── helpers ──────────────────────────────────────────────────────────

def _tenant(request: Request) -> dict:
    """从 app.state.tenant 取当前租户信息"""
    t = getattr(request.app.state, "tenant", None)
    if not t:
        raise HTTPException(403, "未激活")
    return t


def _flag(request: Request, key: str) -> bool:
    return bool(_tenant(request).get("flags", {}).get(key, False))


def _require_flag(request: Request, key: str) -> None:
    if not _flag(request, key):
        raise HTTPException(403, f"当前授权未开放 {key} 功能")


def _range_to_days(range_str: str) -> int:
    """7d / 30d / 90d → int days"""
    if range_str.endswith("d"):
        try:
            return int(range_str[:-1])
        except ValueError:
            pass
    return 7


# ── 1. 今日总览 (所有登录用户可见) ──────────────────────────────────

@router.get("/overview")
async def overview(request: Request, user=Depends(get_current_user)):
    _tenant(request)  # ensure activated
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    with session_factory() as s:
        # 今日订单聚合
        row = (
            s.query(
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.final_amount), 0).label("total_revenue"),
                func.coalesce(func.sum(Order.paid_amount), 0).label("total_paid"),
            )
            .filter(Order.created_at >= today, Order.status.in_(["paid", "completed"]))
            .first()
        )

        # 昨日同比
        yesterday = today - timedelta(days=1)
        yest_row = (
            s.query(func.coalesce(func.sum(Order.final_amount), 0).label("revenue"))
            .filter(
                Order.created_at >= yesterday,
                Order.created_at < today,
                Order.status.in_(["paid", "completed"]),
            )
            .first()
        )
        yest_rev = yest_row[0] if yest_row else 0
        today_rev = row.total_revenue or 0

        # 客单价
        avg_ticket = (today_rev / row.order_count) if row.order_count else 0

        # 近 7 天每日
        week_start = today - timedelta(days=6)
        daily_rows = (
            s.query(
                func.date(Order.created_at).label("d"),
                func.coalesce(func.sum(Order.final_amount), 0).label("rev"),
                func.count(Order.id).label("cnt"),
            )
            .filter(
                Order.created_at >= week_start,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(func.date(Order.created_at))
            .all()
        )
        by_date = {str(r.d): {"revenue": r.rev, "count": r.cnt} for r in daily_rows}
        daily = []
        for i in range(7):
            d = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
            entry = by_date.get(d, {"revenue": 0, "count": 0})
            daily.append({"date": d, **entry})

    # 同比
    yoy = None
    if yest_rev > 0:
        yoy = round((today_rev - yest_rev) / yest_rev * 100, 1)

    return {
        "today_revenue": today_rev,
        "today_count": row.order_count or 0,
        "avg_ticket": avg_ticket,
        "yesterday_revenue": yest_rev,
        "yoy_percent": yoy,
        "daily_7": daily,
    }


# ── 2. 品类分析 ─────────────────────────────────────────────────────

@router.get("/category")
async def category(request: Request, days: int = 30, user=Depends(get_current_user)):
    _tenant(request)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_factory() as s:
        rows = (
            s.query(
                OrderItem.product_name,
                func.sum(OrderItem.subtotal).label("rev"),
                func.sum(OrderItem.quantity).label("qty"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                Order.created_at >= since,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.subtotal).desc())
            .limit(15)
            .all()
        )
    return {
        "range_days": days,
        "top15": [
            {"name": r.product_name, "revenue": r.rev, "quantity": r.qty} for r in rows
        ],
    }


# ── 3. 时段热力 (24h × 7d) ──────────────────────────────────────────

@router.get("/hourly")
async def hourly(request: Request, days: int = 7, user=Depends(get_current_user)):
    _tenant(request)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_factory() as s:
        rows = (
            s.query(
                func.strftime("%H", Order.created_at).label("hour"),
                func.coalesce(func.sum(Order.final_amount), 0).label("rev"),
                func.count(Order.id).label("cnt"),
            )
            .filter(
                Order.created_at >= since,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(func.strftime("%H", Order.created_at))
            .all()
        )
    by_hour = {int(r.hour): {"revenue": r.rev, "count": r.cnt} for r in rows}
    return {
        "range_days": days,
        "hourly": [{"hour": h, **by_hour.get(h, {"revenue": 0, "count": 0})} for h in range(24)],
    }


# ── 4. 趋势对比 (7 / 30 / 90 天) ────────────────────────────────────

@router.get("/trend")
async def trend(request: Request, range: str = "7d", user=Depends(get_current_user)):
    _tenant(request)
    days = _range_to_days(range)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_factory() as s:
        rows = (
            s.query(
                func.date(Order.created_at).label("d"),
                func.coalesce(func.sum(Order.final_amount), 0).label("rev"),
                func.count(Order.id).label("cnt"),
            )
            .filter(
                Order.created_at >= since,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
            .all()
        )
    return {
        "range": range,
        "series": [{"date": str(r.d), "revenue": r.rev, "count": r.cnt} for r in rows],
    }


# ── 5. 会员分析 ─────────────────────────────────────────────────────

@router.get("/member")
async def member_stats(request: Request, user=Depends(get_current_user)):
    _tenant(request)
    _require_flag(request, "member")

    with session_factory() as s:
        total = s.query(func.count(Member.id)).scalar() or 0
        rows = (
            s.query(
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.final_amount), 0).label("rev"),
            )
            .filter(Order.member_id.isnot(None), Order.status.in_(["paid", "completed"]))
            .first()
        )
        non_member_rev = (
            s.query(func.coalesce(func.sum(Order.final_amount), 0))
            .filter(Order.member_id.is_(None), Order.status.in_(["paid", "completed"]))
            .scalar()
            or 0
        )
        member_rev = rows.rev or 0
        total_rev = member_rev + non_member_rev

        # Top-10 会员消费
        top_rows = (
            s.query(
                Member.name,
                Member.card_no,
                func.sum(Order.final_amount).label("rev"),
                func.count(Order.id).label("cnt"),
            )
            .join(Order, Order.member_id == Member.id)
            .filter(Order.status.in_(["paid", "completed"]))
            .group_by(Member.id)
            .order_by(func.sum(Order.final_amount).desc())
            .limit(10)
            .all()
        )

    return {
        "total_members": total,
        "member_revenue": member_rev,
        "non_member_revenue": non_member_rev,
        "member_ratio": round(member_rev / total_rev * 100, 1) if total_rev else 0,
        "top10": [
            {"name": r.name, "card_no": r.card_no, "revenue": r.rev, "count": r.cnt}
            for r in top_rows
        ],
    }


# ── 6. 收银员效率 ───────────────────────────────────────────────────

@router.get("/cashier")
async def cashier_stats(request: Request, days: int = 30, user=Depends(get_current_user)):
    _tenant(request)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_factory() as s:
        rows = (
            s.query(
                Order.cashier_id,
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.final_amount), 0).label("rev"),
            )
            .filter(
                Order.created_at >= since,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(Order.cashier_id)
            .all()
        )
    return {
        "range_days": days,
        "cashiers": [
            {"id": r.cashier_id, "count": r.cnt, "revenue": r.rev} for r in rows
        ],
    }


# ── 7. 门店对比 (仅 chain_view 授权, 即 chain_parent) ────────────────

@router.get("/chain/stores")
async def chain_stores(request: Request, user=Depends(get_current_user)):
    """母店视角：拉取所有子店名称与数据（子店需先 push 到云，此处为本地 stub，云版本通过云端汇总）"""
    t = _tenant(request)
    if t.get("license_type") != "chain_parent":
        raise HTTPException(403, "仅连锁母店可查看跨店对比")

    # 本地 stub：返回本 POS 可作为数据来源的基础信息，实际跨店数据由云端汇总服务提供
    return {
        "parent_tenant_id": t["id"],
        "license_type": t["license_type"],
        "max_stores": t["max_stores"],
        "chain_view_enabled": True,
        "local_only": True,
        "note": "跨店数据需配置云同步后由云端看板展示",
        "flags": t.get("flags", {}),
    }


# ── 租户信息 (前端初始化用) ─────────────────────────────────────────

@router.get("/tenant")
async def tenant_info(request: Request, user=Depends(get_current_user)):
    """返回当前 POS 的 license_store_name / license_type 等前端渲染所需字段"""
    t = _tenant(request)
    flags = t.get("flags", {})
    return {
        "store_name": t.get("license_store_name", "未授权"),
        "license_type": t.get("license_type", "single"),
        "license_tier": t.get("license_tier", "single"),
        "features": {
            "dashboard": flags.get("dashboard", True),
            "cloud_sync": flags.get("cloud_sync", False),
            "chain_view": flags.get("chain_view", False),
            "member": flags.get("member", True),
            "report": flags.get("report", True),
        },
    }

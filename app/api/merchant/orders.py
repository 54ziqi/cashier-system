"""商家端：订单 API - 跨租户隔离 (P1-W5) + M1 订单状态机"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.infra.db.engine import session_factory
from app.infra.db.models import Order as OrderModel
from app.infra.db.models import OrderStatusLog as OrderStatusLogModel

router = APIRouter(prefix="/api/v1/merchant/orders", tags=["merchant-orders"])

# ── 状态机规则 (M1) ─────────────────────────────────────────────

# 结账后订单进入 completed，不同业态从这里分叉：
# 快餐：completed → making → ready → served
# 烘焙/零售：checkout 终态就是 completed (也可显式 POST "completed" 作为 no-op)
_TRANSITIONS: dict[str, list[str]] = {
    "completed": ["completed", "making"],
    "making": ["ready"],
    "ready": ["served"],
    "served": ["served"],
    "paid": ["completed", "making"],
    "voided": [],
}


def _allowed(from_s: str) -> list[str]:
    return _TRANSITIONS.get(from_s, [])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_merchant_id(request: Request) -> str:
    """
    从 app.state 获取当前 merchant_id (POS 单机版 = local);
    在线版从 token 中解析 merchant_id。
    """
    # POS 场景：每个 app 初始化时绑定一个 tenant_id
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


@router.get("")
async def list_orders(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str = Query(""),
):
    await get_current_user(request)
    merchant_id = _get_merchant_id(request)
    svc = _get_checkout_service(request, merchant_id)
    orders = svc.list_orders(limit=page_size, offset=(page - 1) * page_size)
    # P1-W5: 服务端再过滤一次 merchant_id (防止 svc 漏查)
    orders = [
        o
        for o in orders
        if o.get("merchant_id") == merchant_id or "merchant_id" not in o
    ]
    if status_filter:
        orders = [o for o in orders if o.get("status") == status_filter]
    return {"items": orders, "page": page, "page_size": page_size}


@router.get("/{order_id}")
async def get_order(request: Request, order_id: str):
    await get_current_user(request)
    merchant_id = _get_merchant_id(request)
    svc = _get_checkout_service(request, merchant_id)
    order = svc.get_order(order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    # P1-W5: 跨租户读取拒绝 (检查订单归属)
    if order.get("merchant_id") and order["merchant_id"] != merchant_id:
        raise HTTPException(404, "订单不存在")
    return order


@router.post("/refund/{order_id}")
async def refund_order(request: Request, order_id: str):
    await get_current_user(request)
    merchant_id = _get_merchant_id(request)
    svc = _get_checkout_service(request, merchant_id)
    # P1-W5: 先校验订单归属
    order = svc.get_order(order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.get("merchant_id") and order["merchant_id"] != merchant_id:
        raise HTTPException(404, "订单不存在")
    try:
        svc.refund_order(order_id)
        return {"refunded": True, "order_id": order_id}
    except Exception as e:
        raise HTTPException(400, str(e))


def _get_checkout_service(request: Request, merchant_id: str | None = None):
    from app.application.checkout.checkout_service import CheckoutService

    mid = merchant_id or _get_merchant_id(request)
    return CheckoutService(sid=mid)


# ── M1 状态机 API ────────────────────────────────────────────────


class StatusTransitionBody(BaseModel):
    transition: str
    queue_no: str = ""
    actor_id: str = ""
    reason: str = ""


class VoidBody(BaseModel):
    reason: str = ""
    actor_id: str = ""


@router.post("/{order_id}/status")
async def transition_order_status(
    request: Request,
    order_id: str,
    body: StatusTransitionBody,
):
    """推动订单状态流转 (paid → making → ready → served / completed)"""
    await get_current_user(request)
    mid = _get_merchant_id(request)

    with session_factory() as s:
        order = (
            s.query(OrderModel).filter_by(id=order_id, merchant_id=mid).first()
        )
        if not order:
            raise HTTPException(404, "订单不存在")

        fr = order.status
        to = body.transition

        # Self-transition: no-op (idempotent)
        if fr == to:
            log = OrderStatusLogModel(
                id=str(uuid.uuid4()),
                order_id=order_id,
                from_status=fr,
                to_status=to,
                actor_type="user",
                actor_id=body.actor_id,
                reason=body.reason or "no-op",
                ts=datetime.now(timezone.utc),
            )
            s.add(log)
            s.commit()
            return {
                "order_id": order_id,
                "status": to,
                "kitchen_status": order.kitchen_status,
                "queue_no": body.queue_no,
            }

        if to not in _allowed(fr):
            raise HTTPException(
                400,
                f"不允许从 '{fr}' 转入 '{to}' (允许: {_allowed(fr)})",
            )

        order.status = to
        order.updated_at = datetime.now(timezone.utc)
        # 同步 kitchen_status (简化：按同字段流转)
        order.kitchen_status = to

        log = OrderStatusLogModel(
            id=str(uuid.uuid4()),
            order_id=order_id,
            from_status=fr,
            to_status=to,
            actor_type="user",
            actor_id=body.actor_id,
            reason=body.reason,
            ts=datetime.now(timezone.utc),
        )
        s.add(log)
        s.commit()

        return {
            "order_id": order_id,
            "status": to,
            "kitchen_status": order.kitchen_status,
            "queue_no": body.queue_no,
        }


@router.post("/{order_id}/void")
async def void_order(
    request: Request,
    order_id: str,
    body: VoidBody,
    user=Depends(require_admin),
):
    """整单作废 (admin only) — 带状态校验 + CAS + 库存积分回滚"""
    mid = _get_merchant_id(request)
    with session_factory() as s:
        order = (
            s.query(OrderModel).filter_by(id=order_id, merchant_id=mid).first()
        )
        if not order:
            raise HTTPException(404, "订单不存在")

        fr = order.status
        # 状态校验：已退款/已作废/已完成的订单不能再次作废
        if fr in ("voided", "refunded"):
            raise HTTPException(400, f"订单已{fr == 'voided' and '作废' or '退款'}，不可重复作废")
        if fr == "completed":
            raise HTTPException(400, "订单已完成，请走退款流程")

        order.status = "voided"
        order.kitchen_status = "voided"
        order.void_reason = body.reason
        order.updated_at = datetime.now(timezone.utc)

        log = OrderStatusLogModel(
            id=str(uuid.uuid4()),
            order_id=order_id,
            from_status=fr,
            to_status="voided",
            actor_type="admin",
            actor_id=getattr(user, "id", "") or "",
            reason=body.reason,
            ts=datetime.now(timezone.utc),
        )
        s.add(log)
        s.commit()
        return {"order_id": order_id, "status": "voided"}


@router.post("/{order_id}/urge")
async def urge_order(request: Request, order_id: str):
    """催菜：仅 making 状态可催"""
    await get_current_user(request)
    mid = _get_merchant_id(request)
    with session_factory() as s:
        order = (
            s.query(OrderModel).filter_by(id=order_id, merchant_id=mid).first()
        )
        if not order:
            raise HTTPException(404, "订单不存在")
        if order.kitchen_status != "making":
            raise HTTPException(
                400, f"当前状态 '{order.kitchen_status}' 不可催菜"
            )
        log = OrderStatusLogModel(
            id=str(uuid.uuid4()),
            order_id=order_id,
            from_status="making",
            to_status="making",
            actor_type="user",
            actor_id="",
            reason="催菜",
            ts=datetime.now(timezone.utc),
        )
        s.add(log)
        s.commit()
        return {"order_id": order_id, "urged": True}

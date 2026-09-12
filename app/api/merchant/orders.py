"""商家端：订单 API - 跨租户隔离 (P1-W5)"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/merchant/orders", tags=["merchant-orders"])


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

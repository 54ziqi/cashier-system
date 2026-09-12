"""商家端：订单 API"""
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Query, Depends

from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/merchant/orders", tags=["merchant-orders"])


@router.get("")
async def list_orders(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str = Query(""),
):
    user = await get_current_user(request)
    svc = _get_checkout_service(request)
    orders = svc.list_orders(limit=page_size, offset=(page - 1) * page_size)
    if status_filter:
        orders = [o for o in orders if o.get("status") == status_filter]
    return {"items": orders, "page": page, "page_size": page_size}


@router.get("/{order_id}")
async def get_order(request: Request, order_id: str):
    user = await get_current_user(request)
    svc = _get_checkout_service(request)
    order = svc.get_order(order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    return order


@router.post("/refund/{order_id}")
async def refund_order(request: Request, order_id: str, _admin=Depends(require_admin)):
    svc = _get_checkout_service(request)
    try:
        svc.refund_order(order_id)
        return {"refunded": True, "order_id": order_id}
    except Exception as e:
        raise HTTPException(400, str(e))


def _get_checkout_service(request: Request):
    from app.application.checkout.checkout_service import CheckoutService
    return CheckoutService(sid="local")

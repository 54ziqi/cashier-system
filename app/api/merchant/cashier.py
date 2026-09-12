"""商家端：收银/结算 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant-cashier"])


class CheckoutItem(BaseModel):
    product_id: str
    quantity: float = 1
    weight: float = 0
    discount: int = 0


class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]
    pay_method: str = "cash"  # cash / member_balance / wechat / alipay
    member_id: str = ""
    cash_amount: int = 0  # 现金实付（分）
    idempotency_key: str = ""


class SuspendRequest(BaseModel):
    items: list[CheckoutItem]
    note: str = ""


@router.post("/cashier/checkout")
async def checkout(request: Request, data: CheckoutRequest):
    user = await get_current_user(request)

    from app.application.checkout.checkout_service import CheckoutError, CheckoutService

    checkout_svc = CheckoutService(sid="local")

    try:
        order_items = [item.model_dump() for item in data.items]

        # 原子结账：创建订单 + 扣库存 + 支付在同一事务中
        result = checkout_svc.checkout(
            items=order_items,
            pay_method=data.pay_method,
            cashier_id=user.user_id,
            member_id=data.member_id,
            cash_amount=data.cash_amount,
            idempotency_key=data.idempotency_key,
        )

        order = result["order"]
        payment = result["payment"]

        return {
            "success": True,
            "order_id": order.id,
            "order_no": order.order_no,
            "final_amount": order.final_amount,
            "final_amount_yuan": round(order.final_amount / 100, 2),
            "paid_amount": payment["amount"],
            "change": payment.get("change", 0),
            "change_yuan": round(payment.get("change", 0) / 100, 2),
        }

    except CheckoutError as e:
        raise HTTPException(400, str(e))


@router.get("/members")
async def list_members(
    request: Request,
    phone: str = "",
    page: int = 1,
    page_size: int = 50,
):
    user = await get_current_user(request)
    from app.application.member.member_service import MemberService

    svc = MemberService(merchant_id="local")
    if phone:
        member = svc.find_by_phone(phone)
        return {"items": [member] if member else [], "total": 1 if member else 0}
    return svc.list_members(page=page, page_size=page_size)


@router.get("/members/{member_id}")
async def get_member(request: Request, member_id: str):
    user = await get_current_user(request)
    from app.application.member.member_service import MemberService

    svc = MemberService(merchant_id="local")
    member = svc.get_member(member_id)
    if not member:
        raise HTTPException(404, "会员不存在")
    return member


@router.post("/members")
async def create_member(request: Request, data: dict):
    user = await get_current_user(request)
    from app.application.member.member_service import MemberService

    svc = MemberService(merchant_id="local")
    try:
        return svc.create_member(data)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/members/{member_id}/recharge")
async def recharge_member(
    request: Request, member_id: str, amount: float = 0, user=Depends(require_admin)
):
    from app.application.member.member_service import MemberService

    svc = MemberService(merchant_id="local")
    try:
        return svc.recharge(member_id, amount)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/cart/suspended")
async def list_suspended(request: Request):
    user = await get_current_user(request)
    return {"items": [], "total": 0}  # 挂单暂由前端 sessionStorage 管理

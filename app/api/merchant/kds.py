"""商家端：KDS 厨房制作单 API (M5)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_user
from app.application.kds.kds_service import KdsService

router = APIRouter(prefix="/api/v1/merchant/kds", tags=["merchant-kds"])


# ── helpers ──────────────────────────────────────────────────

def _get_merchant_id(request: Request) -> str:
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


def _kds_svc(request: Request) -> KdsService:
    return KdsService(merchant_id=_get_merchant_id(request))


# ── KDS 队列 & 状态流转 ─────────────────────────────────────

@router.get("/queue")
async def get_queue(
    request: Request,
    station: str = Query(""),
    user=Depends(get_current_user),
):
    """获取 KDS 待制作队列"""
    svc = _kds_svc(request)
    return {"items": svc.get_queue(station=station)}


@router.get("/tickets/{order_id}")
async def get_order_tickets(request: Request, order_id: str, user=Depends(get_current_user)):
    """获取某订单的所有 KDS 制作单"""
    svc = _kds_svc(request)
    return {"items": svc.get_order_tickets(order_id)}


@router.post("/tickets/{ticket_id}/start")
async def start_cooking(request: Request, ticket_id: str, user=Depends(get_current_user)):
    """开始制作: pending → cooking"""
    svc = _kds_svc(request)
    try:
        return svc.mark_cooking(ticket_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tickets/{ticket_id}/done")
async def mark_done(request: Request, ticket_id: str, user=Depends(get_current_user)):
    """制作完成: cooking → ready"""
    svc = _kds_svc(request)
    try:
        return svc.mark_ready(ticket_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tickets/{ticket_id}/serve")
async def mark_served(request: Request, ticket_id: str, user=Depends(get_current_user)):
    """出餐: ready → served"""
    svc = _kds_svc(request)
    try:
        return svc.mark_served(ticket_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tickets/{ticket_id}/void")
async def void_ticket(request: Request, ticket_id: str, user=Depends(get_current_user)):
    """作废制作单"""
    svc = _kds_svc(request)
    try:
        return svc.mark_void(ticket_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tickets/{ticket_id}/fire")
async def fire_ticket(request: Request, ticket_id: str, user=Depends(get_current_user)):
    """叫起 (KDS)：标记 fire_at"""
    svc = _kds_svc(request)
    try:
        return svc.fire_ticket(ticket_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

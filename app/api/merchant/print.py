"""商家端：ESC/POS 打印 API (M5)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.application.print.escpos_service import EscPosService

router = APIRouter(prefix="/api/v1/merchant/print", tags=["merchant-print"])


# ── helpers ──────────────────────────────────────────────────

def _get_merchant_id(request: Request) -> str:
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


def _print_svc(request: Request) -> EscPosService:
    return EscPosService(merchant_id=_get_merchant_id(request))


# ── schemas ──────────────────────────────────────────────────

class PrintReceiptBody(BaseModel):
    order_id: str


class PrintLabelBody(BaseModel):
    order_id: str


class PrintTestBody(BaseModel):
    target: str = "default"


# ── Endpoints ────────────────────────────────────────────────

@router.post("/receipt")
async def print_receipt(request: Request, body: PrintReceiptBody, user=Depends(get_current_user)):
    """打印小票"""
    from app.application.checkout.checkout_service import CheckoutService

    checkout_svc = CheckoutService(sid=_get_merchant_id(request))
    order = checkout_svc.get_order(body.order_id)
    if not order:
        raise HTTPException(404, "订单不存在")

    esc_svc = _print_svc(request)
    raw = esc_svc.build_receipt(order)
    job = esc_svc.enqueue("receipt", "default_receipt", raw)
    return {"job_id": job.id, "status": "enqueued"}


@router.post("/label")
async def print_label(request: Request, body: PrintLabelBody, user=Depends(get_current_user)):
    """打印标签"""
    from app.infra.db.engine import session_factory
    from app.infra.db.models import OrderItem

    mid = _get_merchant_id(request)
    with session_factory() as s:
        items = s.query(OrderItem).filter_by(order_id=body.order_id).all()
        if not items:
            raise HTTPException(404, "订单无明细")

    esc_svc = _print_svc(request)
    jobs = []
    for item in items:
        label_data = {
            "product_name": item.product_name,
            "spec_text": item.spec_text or "",
        }
        raw = esc_svc.build_label(label_data)
        job = esc_svc.enqueue("label", "default_label", raw)
        jobs.append(job.id)

    return {"job_ids": jobs, "status": "enqueued"}


@router.post("/test")
async def print_test(request: Request, body: PrintTestBody, user=Depends(get_current_user)):
    """打印测试页"""
    esc_svc = _print_svc(request)
    job = esc_svc.print_test(target=body.target)
    return {"job_id": job.id, "status": "enqueued"}


@router.get("/jobs")
async def list_print_jobs(
    request: Request,
    status: str = "",
    user=Depends(get_current_user),
):
    """列出打印任务"""
    esc_svc = _print_svc(request)
    return {"items": esc_svc.list_jobs(status_filter=status)}

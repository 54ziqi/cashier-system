"""商家端：财务报表/离线缓存 API (M5)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.application.finance.offline_cache_service import OfflineCacheService
from app.application.finance.report_service import ReportService

router = APIRouter(prefix="/api/v1/merchant/finance", tags=["merchant-finance"])


# ── helpers ──────────────────────────────────────────────────

def _get_merchant_id(request: Request) -> str:
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


def _report_svc(request: Request) -> ReportService:
    return ReportService(merchant_id=_get_merchant_id(request))


def _offline_svc(request: Request) -> OfflineCacheService:
    settings = request.app.state.settings
    return OfflineCacheService(settings=settings)


def _parse_dates(start: str = "", end: str = ""):
    now = datetime.now(timezone.utc)
    if start:
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            s = now - timedelta(days=1)
    else:
        s = now - timedelta(days=1)

    if end:
        try:
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            e = now
    else:
        e = now
    return s, e


# ── Profit Report ─────────────────────────────────────────────

@router.get("/reports/profit")
async def profit_report(
    request: Request,
    start: str = Query(""),
    end: str = Query(""),
    user=Depends(get_current_user),
):
    svc = _report_svc(request)
    s, e = _parse_dates(start, end)
    return svc.generate_profit_report(start=s, end=e)


# ── Cash Reconciliation ───────────────────────────────────────

@router.get("/reports/cash")
async def cash_report(
    request: Request,
    start: str = Query(""),
    end: str = Query(""),
    user=Depends(get_current_user),
):
    svc = _report_svc(request)
    s, e = _parse_dates(start, end)
    return svc.generate_cash_reconciliation(start=s, end=e)


# ── Staff Performance ─────────────────────────────────────────

@router.get("/reports/staff")
async def staff_report(
    request: Request,
    start: str = Query(""),
    end: str = Query(""),
    user=Depends(get_current_user),
):
    svc = _report_svc(request)
    s, e = _parse_dates(start, end)
    return svc.generate_staff_performance(start=s, end=e)


# ── Dashboard Metrics ─────────────────────────────────────────

@router.get("/reports/dashboard")
async def dashboard_metrics(
    request: Request,
    days: int = Query(7, ge=1, le=365),
    user=Depends(get_current_user),
):
    svc = _report_svc(request)
    return svc.get_dashboard_metrics(days=days)


# ── CSV Export ────────────────────────────────────────────────

@router.get("/reports/export", response_class=PlainTextResponse)
async def export_report(
    request: Request,
    type: str = Query("profit"),
    format: str = Query("csv"),
    user=Depends(get_current_user),
):
    svc = _report_svc(request)
    s, e = _parse_dates()
    if type == "profit":
        report = svc.generate_profit_report(start=s, end=e)
    elif type == "cash":
        report = svc.generate_cash_reconciliation(start=s, end=e)
    elif type == "staff":
        report = svc.generate_staff_performance(start=s, end=e)
    else:
        raise HTTPException(400, f"无效报表类型: {type}")

    path = svc.export_csv(report)
    content = open(path).read()
    return PlainTextResponse(content=content, media_type="text/csv")


# ── Offline Status ────────────────────────────────────────────

@router.get("/offline/status")
async def offline_status(request: Request, user=Depends(get_current_user)):
    """离线缓存状态"""
    svc = _offline_svc(request)
    cached = svc.get_cached()
    valid = svc.is_valid()
    return {
        "cached": cached is not None,
        "valid": valid,
        "status": cached.get("status", "none") if cached else "none",
        "expired_at": cached.get("expired_at", "") if cached else "",
    }

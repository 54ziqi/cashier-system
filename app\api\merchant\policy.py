"""商家端：M6 策略下发 / 门店调拨 / 集团分账 API"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.application.chain.policy_client import PolicyClient
from app.application.chain.settlement_service import SettlementService
from app.application.chain.transfer_service import TransferService

router = APIRouter(prefix="/api/v1/merchant/chain", tags=["chain"])


# ── helpers ──────────────────────────────────────────────────

def _get_merchant_id(request: Request) -> str:
    """从 app state 获取当前租户 ID"""
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


def _parse_iso(ts: str) -> datetime:
    """解析 ISO 时间戳字符串"""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ── 请求体模型 ───────────────────────────────────────────────


class PullIn(BaseModel):
    since_ts: int = 0


class ApplyIn(BaseModel):
    push_id: str
    policy_type: str


class TransferCreateIn(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    items: list[dict] = Field(..., min_length=1)


class SettlementCalcIn(BaseModel):
    period_start: str
    period_end: str
    hq_pct: int = 5


# ── GET /policies/status ────────────────────────────────────


@router.get("/policies/status")
async def get_policy_status(
    request: Request,
    user=Depends(get_current_user),
):
    """查看本地各策略类型的最新接收版本"""
    merchant_id = _get_merchant_id(request)
    client = PolicyClient(merchant_id=merchant_id)
    return {
        "tenant_id": merchant_id,
        "local_versions": {
            "menu": client.get_local_version("menu"),
            "prices": client.get_local_version("prices"),
            "members": client.get_local_version("members"),
            "promotions": client.get_local_version("promotions"),
        },
    }


# ── POST /policies/pull ─────────────────────────────────────


@router.post("/policies/pull")
async def pull_policies(
    body: PullIn,
    request: Request,
    user=Depends(get_current_user),
):
    """从云端拉取最新策略变更并逐条应用"""
    merchant_id = _get_merchant_id(request)
    client = PolicyClient(merchant_id=merchant_id)

    policies = client.fetch_policies(since_ts=body.since_ts)
    applied = []
    failed = []

    for pol in policies:
        ptype = pol.get("policy_type", "")
        pid = pol.get("id", "")
        payload = pol.get("payload", {})

        try:
            if ptype == "menu":
                result = client.apply_menu_policy(payload)
            elif ptype in ("prices", "price"):
                result = client.apply_price_policy(payload)
            elif ptype == "members":
                result = client.apply_member_policy(payload)
            elif ptype == "promotions":
                result = client.apply_promotion_policy(payload)
            else:
                result = {"ok": False, "error": f"unknown type: {ptype}"}

            client.record_receipt(
                push_id=pid, policy_type=ptype, status="applied"
            )
            applied.append({"push_id": pid, "policy_type": ptype, **result})
        except Exception as e:
            client.record_receipt(
                push_id=pid,
                policy_type=ptype,
                status="failed",
                conflict_detail=str(e),
            )
            failed.append({"push_id": pid, "error": str(e)})

    return {"applied": applied, "failed": failed}


# ── POST /policies/apply ────────────────────────────────────


@router.post("/policies/apply")
async def apply_policy(
    body: ApplyIn,
    request: Request,
    user=Depends(get_current_user),
):
    """手动触发单条策略的本地应用"""
    merchant_id = _get_merchant_id(request)
    client = PolicyClient(merchant_id=merchant_id)

    # pull
    client.record_receipt(
        push_id=body.push_id,
        policy_type=body.policy_type,
        status="acknowledged",
    )
    return {"ok": True, "push_id": body.push_id, "policy_type": body.policy_type}


# ── GET /transfers ──────────────────────────────────────────


@router.get("/transfers")
async def list_transfers(
    request: Request,
    status: str = "",
    user=Depends(get_current_user),
):
    """列出门店调拨单"""
    merchant_id = _get_merchant_id(request)
    svc = TransferService(merchant_id=merchant_id)
    return svc.list_transfers(status=status)


# ── POST /transfers ─────────────────────────────────────────


@router.post("/transfers")
async def create_transfer(
    body: TransferCreateIn,
    request: Request,
    user=Depends(get_current_user),
):
    """创建调拨单"""
    merchant_id = _get_merchant_id(request)
    svc = TransferService(merchant_id=merchant_id)
    try:
        result = svc.create(
            from_warehouse_id=body.from_warehouse_id,
            to_warehouse_id=body.to_warehouse_id,
            items=body.items,
            operator_id=user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── POST /transfers/{id}/ship ──────────────────────────────


@router.post("/transfers/{transfer_id}/ship")
async def ship_transfer(
    transfer_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """发货：draft → shipping"""
    merchant_id = _get_merchant_id(request)
    svc = TransferService(merchant_id=merchant_id)
    try:
        return svc.ship(transfer_id=transfer_id, operator_id=user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── POST /transfers/{id}/receive ────────────────────────────


@router.post("/transfers/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """收货：shipping → received"""
    merchant_id = _get_merchant_id(request)
    svc = TransferService(merchant_id=merchant_id)
    try:
        return svc.receive(transfer_id=transfer_id, operator_id=user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── GET /settlements ────────────────────────────────────────


@router.get("/settlements")
async def list_settlements(
    request: Request,
    period_start: str = "",
    period_end: str = "",
    user=Depends(get_current_user),
):
    """列出集团分账结算单"""
    merchant_id = _get_merchant_id(request)
    svc = SettlementService(merchant_id=merchant_id)
    ps = _parse_iso(period_start) if period_start else None
    pe = _parse_iso(period_end) if period_end else None
    return svc.list_settlements(period_start=ps, period_end=pe)


# ── POST /settlements/calculate ─────────────────────────────


@router.post("/settlements/calculate")
async def calculate_settlement(
    body: SettlementCalcIn,
    request: Request,
    user=Depends(get_current_user),
):
    """计算期间收入并生成结算单"""
    merchant_id = _get_merchant_id(request)
    svc = SettlementService(merchant_id=merchant_id)
    try:
        ps = _parse_iso(body.period_start)
        pe = _parse_iso(body.period_end)
        return svc.calculate(
            period_start=ps, period_end=pe, hq_pct=body.hq_pct
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── POST /settlements/{id}/confirm ──────────────────────────


@router.post("/settlements/{settlement_id}/confirm")
async def confirm_settlement(
    settlement_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """确认结算单：draft → confirmed"""
    merchant_id = _get_merchant_id(request)
    svc = SettlementService(merchant_id=merchant_id)
    try:
        return svc.confirm(settlement_id=settlement_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

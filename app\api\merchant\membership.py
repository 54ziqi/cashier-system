"""商家端：会员 CRM API (M2)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant-membership"])


# ── Pydantic Schemas ──────────────────────────────────────────

class DepositBody(BaseModel):
    amount: int  # 分
    gift_rule: dict | None = None  # {threshold: 分, gift: 分}
    ref_table: str = ""
    ref_id: str = ""
    note: str = ""


class ConsumeBody(BaseModel):
    amount: int
    ref_table: str = "manual"
    ref_id: str = ""
    note: str = ""


class RefundBody(BaseModel):
    amount: int
    ref_id: str


class TransferBody(BaseModel):
    to_member_id: str
    amount: int


class LevelUpdateBody(BaseModel):
    name: str | None = None
    min_spend: int | None = None
    min_points: int | None = None
    discount_pct: int | None = None
    benefits_json: str | None = None
    sort_order: int | None = None


class TagBody(BaseModel):
    tag: str
    value: str = ""


# ── 会员钱包 ───────────────────────────────────────────────────

@router.post("/members/{member_id}/deposit")
async def deposit(
    request: Request,
    member_id: str,
    body: DepositBody,
    user=Depends(require_admin),
):
    from app.application.member.wallet_service import WalletError, WalletService

    svc = WalletService(merchant_id="local")
    try:
        return svc.deposit(
            member_id=member_id,
            amount=body.amount,
            operator_id=user.user_id,
            ref_table=body.ref_table,
            ref_id=body.ref_id,
            note=body.note,
            gift_rule=body.gift_rule,
        )
    except WalletError as e:
        raise HTTPException(400, str(e))


@router.post("/members/{member_id}/consume")
async def consume(
    request: Request,
    member_id: str,
    body: ConsumeBody,
    user=Depends(require_admin),
):
    from app.application.member.wallet_service import WalletError, WalletService

    svc = WalletService(merchant_id="local")
    try:
        return svc.consume(
            member_id=member_id,
            amount=body.amount,
            ref_table=body.ref_table,
            ref_id=body.ref_id,
            note=body.note,
        )
    except WalletError as e:
        raise HTTPException(400, str(e))


@router.post("/members/{member_id}/refund")
async def refund_wallet(
    request: Request,
    member_id: str,
    body: RefundBody,
    user=Depends(require_admin),
):
    from app.application.member.wallet_service import WalletError, WalletService

    svc = WalletService(merchant_id="local")
    try:
        return svc.refund(
            member_id=member_id,
            amount=body.amount,
            ref_table="orders",
            ref_id=body.ref_id,
        )
    except WalletError as e:
        raise HTTPException(400, str(e))


@router.get("/members/{member_id}/wallet")
async def get_wallet(request: Request, member_id: str):
    from app.application.member.wallet_service import WalletError, WalletService
    from app.application.member.points_service import PointsError, PointsService
    from app.application.member.level_service import LevelError, LevelService

    wallet_svc = WalletService(merchant_id="local")
    points_svc = PointsService(merchant_id="local")
    level_svc = LevelService(merchant_id="local")

    try:
        balance = wallet_svc.get_balance(member_id)
        points = points_svc.get_points(member_id)
    except (WalletError, PointsError) as e:
        raise HTTPException(404, str(e))

    wallet_txns = wallet_svc.list_txns(member_id)
    points_txns = points_svc.list_txns(member_id)

    try:
        level_info = level_svc.get_member_level(member_id)
    except LevelError:
        level_info = {"level": "unknown"}

    return {
        "member_id": member_id,
        "balance": balance,
        "points": points,
        "level": level_info.get("level", ""),
        "level_info": level_info.get("level_info"),
        "wallet_txns": wallet_txns,
        "points_txns": points_txns,
    }


@router.post("/members/{member_id}/transfer")
async def transfer(
    request: Request,
    member_id: str,
    body: TransferBody,
    user=Depends(require_admin),
):
    from app.application.member.wallet_service import WalletError, WalletService

    svc = WalletService(merchant_id="local")
    try:
        return svc.transfer(
            from_id=member_id,
            to_id=body.to_member_id,
            amount=body.amount,
            operator_id=user.user_id,
        )
    except WalletError as e:
        raise HTTPException(400, str(e))


# ── 会员等级 ───────────────────────────────────────────────────

@router.get("/members/levels")
async def list_levels(request: Request):
    from app.application.member.level_service import LevelService

    svc = LevelService(merchant_id="local")
    return {"items": svc.list_levels()}


@router.post("/members/levels/init")
async def init_levels(request: Request, user=Depends(require_admin)):
    from app.application.member.level_service import LevelService

    svc = LevelService(merchant_id="local")
    return {"items": svc.init_defaults()}


@router.put("/members/levels/{level_id}")
async def update_level(
    request: Request, level_id: str, body: LevelUpdateBody, user=Depends(require_admin)
):
    from app.application.member.level_service import LevelError, LevelService

    svc = LevelService(merchant_id="local")
    try:
        return svc.update_level(level_id, body.model_dump(exclude_unset=True))
    except LevelError as e:
        raise HTTPException(400, str(e))


@router.post("/members/{member_id}/level/evaluate")
async def evaluate_level(request: Request, member_id: str):
    from app.application.member.level_service import LevelError, LevelService

    svc = LevelService(merchant_id="local")
    try:
        return svc.evaluate(member_id)
    except LevelError as e:
        raise HTTPException(400, str(e))


# ── 会员标签 ───────────────────────────────────────────────────

@router.get("/members/{member_id}/tags")
async def list_tags(request: Request, member_id: str):
    from app.application.member.tag_service import TagService

    svc = TagService(merchant_id="local")
    return {"items": svc.list_tags(member_id)}


@router.post("/members/{member_id}/tags")
async def add_tag(
    request: Request, member_id: str, body: TagBody, user=Depends(require_admin)
):
    from app.application.member.tag_service import TagService

    svc = TagService(merchant_id="local")
    return svc.add_tag(member_id, body.tag, body.value, source="manual")


@router.delete("/members/{member_id}/tags/{tag_id}")
async def remove_tag(request: Request, member_id: str, tag_id: str, user=Depends(require_admin)):
    from app.application.member.tag_service import TagError, TagService

    svc = TagService(merchant_id="local")
    try:
        svc.remove_tag(tag_id)
        return {"deleted": True, "tag_id": tag_id}
    except TagError as e:
        raise HTTPException(400, str(e))


# ── 营销活动 ───────────────────────────────────────────────────

class BirthdayCheckBody(BaseModel):
    pass


class DormantCheckBody(BaseModel):
    days: int = 30


class SendCouponBody(BaseModel):
    campaign_type: str = "manual"
    template_id: str = ""
    member_ids: list[str]


@router.post("/members/campaigns/birthday-check")
async def birthday_check(request: Request, user=Depends(require_admin)):
    from app.application.campaign.campaign_service import CampaignService

    svc = CampaignService(merchant_id="local")
    return {"members": svc.check_birthday()}


@router.post("/members/campaigns/dormant-check")
async def dormant_check(
    request: Request, body: DormantCheckBody, user=Depends(require_admin)
):
    from app.application.campaign.campaign_service import CampaignService

    svc = CampaignService(merchant_id="local")
    return {"members": svc.check_dormant(body.days)}


@router.post("/members/campaigns/send-coupon")
async def send_coupon(
    request: Request, body: SendCouponBody, user=Depends(require_admin)
):
    from app.application.campaign.campaign_service import CampaignError, CampaignService

    svc = CampaignService(merchant_id="local")
    try:
        results = svc.send_batch_coupons(
            template_id=body.template_id,
            member_ids=body.member_ids,
            campaign_type=body.campaign_type,
        )
        return {"results": results}
    except CampaignError as e:
        raise HTTPException(400, str(e))

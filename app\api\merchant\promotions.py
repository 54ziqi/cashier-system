"""商家端：促销规则引擎 API (M3)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant-promotions"])


# ── Pydantic Schemas ──────────────────────────────────────────

class RuleCreateBody(BaseModel):
    name: str
    type: str  # full_reduction / discount / gift / time_special / coupon_grant
    priority: int = 0
    conditions: dict = {}
    actions: dict = {}
    start_at: str | None = None
    end_at: str | None = None
    stackable: int = 0
    status: str = "active"


class RuleUpdateBody(BaseModel):
    name: str | None = None
    priority: int | None = None
    conditions: dict | None = None
    actions: dict | None = None
    start_at: str | None = None
    end_at: str | None = None
    stackable: int | None = None
    status: str | None = None


class TemplateCreateBody(BaseModel):
    name: str
    type: str  # amount / percentage
    value: int
    min_amount: int = 0
    total_qty: int = 0
    valid_days: int = 30
    applicable_products: list[str] = []


class CouponIssueBody(BaseModel):
    template_id: str
    member_id: str


class CouponRedeemBody(BaseModel):
    code: str


# ── 促销规则 ───────────────────────────────────────────────────

@router.get("/promotions/rules")
async def list_rules(request: Request, status: str = Query("active")):
    from app.application.promotion.rule_engine import RuleEngine

    engine = RuleEngine(merchant_id="local")
    return {"items": engine.list_rules(status=status)}


@router.post("/promotions/rules")
async def create_rule(request: Request, body: RuleCreateBody, user=Depends(require_admin)):
    from app.application.promotion.rule_engine import RuleEngine, RuleError

    engine = RuleEngine(merchant_id="local")
    try:
        return engine.create_rule(body.model_dump())
    except RuleError as e:
        raise HTTPException(400, str(e))


@router.put("/promotions/rules/{rule_id}")
async def update_rule(
    request: Request, rule_id: str, body: RuleUpdateBody, user=Depends(require_admin)
):
    from app.application.promotion.rule_engine import RuleEngine, RuleError

    engine = RuleEngine(merchant_id="local")
    try:
        return engine.update_rule(rule_id, body.model_dump(exclude_unset=True))
    except RuleError as e:
        raise HTTPException(400, str(e))


@router.delete("/promotions/rules/{rule_id}")
async def delete_rule(request: Request, rule_id: str, user=Depends(require_admin)):
    from app.application.promotion.rule_engine import RuleEngine, RuleError

    engine = RuleEngine(merchant_id="local")
    try:
        engine.delete_rule(rule_id)
        return {"deleted": True, "rule_id": rule_id}
    except RuleError as e:
        raise HTTPException(400, str(e))


@router.post("/promotions/rules/{rule_id}/toggle")
async def toggle_rule(request: Request, rule_id: str, user=Depends(require_admin)):
    from app.application.promotion.rule_engine import RuleEngine, RuleError

    engine = RuleEngine(merchant_id="local")
    try:
        return engine.toggle_rule(rule_id)
    except RuleError as e:
        raise HTTPException(400, str(e))


# ── 优惠券模板 ─────────────────────────────────────────────────

@router.get("/promotions/templates")
async def list_templates(request: Request, status: str = Query("active")):
    from app.application.promotion.coupon_service import CouponService

    svc = CouponService(merchant_id="local")
    return {"items": svc.list_templates(status=status)}


@router.post("/promotions/templates")
async def create_template(
    request: Request, body: TemplateCreateBody, user=Depends(require_admin)
):
    from app.application.promotion.coupon_service import CouponError, CouponService

    svc = CouponService(merchant_id="local")
    try:
        return svc.create_template(body.model_dump())
    except CouponError as e:
        raise HTTPException(400, str(e))


# ── 优惠券实例 ─────────────────────────────────────────────────

@router.post("/promotions/coupons/issue")
async def issue_coupon(
    request: Request, body: CouponIssueBody, user=Depends(require_admin)
):
    from app.application.promotion.coupon_service import CouponError, CouponService

    svc = CouponService(merchant_id="local")
    try:
        coupon = svc.issue(body.template_id, body.member_id)
        return {
            "id": coupon.id,
            "template_id": coupon.template_id,
            "member_id": coupon.member_id,
            "code": coupon.code,
            "status": coupon.status,
        }
    except CouponError as e:
        raise HTTPException(400, str(e))


@router.post("/promotions/coupons/redeem")
async def redeem_coupon(
    request: Request, body: CouponRedeemBody, user=Depends(require_admin)
):
    from app.application.promotion.coupon_service import CouponError, CouponService

    svc = CouponService(merchant_id="local")
    try:
        # redeem 需要 order_id,此处从 body 或 request header 中取
        order_id = request.headers.get("x-order-id", "")
        result = svc.redeem(body.code, order_id)
        return result
    except CouponError as e:
        raise HTTPException(400, str(e))


@router.get("/promotions/coupons/mine")
async def list_my_coupons(
    request: Request,
    member_id: str = Query(...),
    status: str = Query("unused"),
):
    from app.application.promotion.coupon_service import CouponService

    svc = CouponService(merchant_id="local")
    return {"items": svc.list_member_coupons(member_id, status=status)}


@router.get("/promotions/coupons/validate")
async def validate_coupon(request: Request, code: str = Query(...)):
    from app.application.promotion.coupon_service import CouponService

    svc = CouponService(merchant_id="local")
    return svc.validate_coupon(code)


# ── 规则引擎评估(调试用) ──────────────────────────────────────

class EvaluateBody(BaseModel):
    member_id: str = ""
    items: list[dict] = []
    subtotal: int = 0
    time: str = ""


@router.post("/promotions/rules/evaluate")
async def evaluate_rules(request: Request, body: EvaluateBody):
    from app.application.promotion.rule_engine import RuleEngine

    engine = RuleEngine(merchant_id="local")
    return engine.evaluate(body.model_dump())

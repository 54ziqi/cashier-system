"""管理员端：商户管理 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/admin/merchants", tags=["admin-merchants"])


class MerchantCreate(BaseModel):
    name: str
    contact_name: str = ""
    phone: str = ""
    license_type: str = "free"


async def _require_admin(user=Depends(get_current_user)):
    """校验当前用户是否为管理员"""
    if user.role != "merchant_admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


@router.get("")
async def list_merchants(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    user: dict = Depends(_require_admin),
):
    return {"items": [], "total": 0, "page": page, "stub": True}


@router.post("")
async def create_merchant(
    request: Request,
    data: MerchantCreate,
    user: dict = Depends(_require_admin),
):
    return {"id": "demo", "created": True, "stub": True}


@router.put("/{merchant_id}")
async def update_merchant(
    request: Request,
    merchant_id: str,
    data: dict,
    user: dict = Depends(_require_admin),
):
    return {"id": merchant_id, "updated": True, "stub": True}


@router.delete("/{merchant_id}")
async def disable_merchant(
    request: Request,
    merchant_id: str,
    user: dict = Depends(_require_admin),
):
    return {"id": merchant_id, "disabled": True, "stub": True}

"""管理员端：授权管理 API"""
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Depends

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/admin/licenses", tags=["admin-licenses"])


async def _require_admin(user=Depends(get_current_user)):
    """校验当前用户是否为管理员"""
    if user.role != "merchant_admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


@router.get("")
async def list_licenses(
    request: Request,
    user: dict = Depends(_require_admin),
):
    return {"items": [], "total": 0, "stub": True}


@router.post("")
async def issue_license(
    request: Request,
    data: dict,
    user: dict = Depends(_require_admin),
):
    return {"license_key": "LIC-DEMO-XXXX", "issued": True, "stub": True}


@router.put("/{license_id}/disable")
async def disable_license(
    request: Request,
    license_id: str,
    user: dict = Depends(_require_admin),
):
    return {"id": license_id, "disabled": True, "stub": True}

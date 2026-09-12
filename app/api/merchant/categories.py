"""商家端：商品分类 API"""
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/merchant/categories", tags=["merchant-categories"])


class CategoryCreate(BaseModel):
    name: str
    parent_id: str = ""
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    sort_order: int | None = None


@router.get("")
async def list_categories(request: Request):
    user = await get_current_user(request)
    svc = _svc(request)
    return svc.list_categories()


@router.get("/{cat_id}")
async def get_category(request: Request, cat_id: str):
    user = await get_current_user(request)
    svc = _svc(request)
    cat = svc.get_category(cat_id)
    if not cat:
        raise HTTPException(404, "分类不存在")
    return cat


@router.post("", status_code=201)
async def create_category(request: Request, data: CategoryCreate):
    user = await get_current_user(request)
    svc = _svc(request)
    return svc.create_category(data.model_dump())


@router.put("/{cat_id}")
async def update_category(request: Request, cat_id: str, data: CategoryUpdate):
    user = await get_current_user(request)
    svc = _svc(request)
    result = svc.update_category(cat_id, {k: v for k, v in data.model_dump().items() if v is not None})
    if not result:
        raise HTTPException(404, "分类不存在")
    return result


@router.delete("/{cat_id}")
async def delete_category(request: Request, cat_id: str):
    user = await get_current_user(request)
    svc = _svc(request)
    if svc.delete_category(cat_id):
        return {"deleted": True}
    raise HTTPException(404, "分类不存在")


def _svc(request: Request):
    from app.application.product.category_service import CategoryService
    return CategoryService(merchant_id="local")

"""商家端：商品 API"""
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/merchant/products", tags=["merchant-products"])


class ProductCreate(BaseModel):
    name: str
    price: int  # 分
    barcode: str = ""
    category_id: str = ""
    cost_price: int = 0
    stock: float = 0
    unit: str = "pcs"
    is_weighing: bool = False
    icon: str = "📦"


class ProductUpdate(BaseModel):
    name: str | None = None
    price: int | None = None
    barcode: str | None = None
    cost_price: int | None = None
    stock: float | None = None
    unit: str | None = None
    is_weighing: bool | None = None
    status: str | None = None


@router.get("")
async def list_products(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str = Query(""),
    category_id: str = Query(""),
    q: str = Query(""),
):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    return svc.list_products(page=page, page_size=page_size, status=status,
                              category_id=category_id, q=q)


@router.get("/search")
async def search_products(
    request: Request,
    q: str = Query("", min_length=0),
    category_id: str = Query(""),
):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    if category_id:
        return svc.list_products(page=1, page_size=200, category_id=category_id, q=q)["items"]
    return svc.search(q)


@router.get("/barcode/{barcode}")
async def get_by_barcode(request: Request, barcode: str):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    product = svc.get_by_barcode(barcode)
    if not product:
        raise HTTPException(404, "商品不存在")
    return product


@router.get("/{product_id}")
async def get_product(request: Request, product_id: str):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    product = svc.get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    return product


@router.post("", status_code=201)
async def create_product(request: Request, data: ProductCreate):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    return svc.create_product(data.model_dump())


@router.put("/{product_id}")
async def update_product(request: Request, product_id: str, data: ProductUpdate):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    result = svc.update_product(product_id, {k: v for k, v in data.model_dump().items() if v is not None})
    if not result:
        raise HTTPException(404, "商品不存在")
    return result


@router.delete("/{product_id}")
async def delete_product(request: Request, product_id: str):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    svc.delete_product(product_id)
    return {"deleted": True}


def _get_product_service(request: Request):
    from app.application.product.product_service import ProductService
    return ProductService(merchant_id="local")

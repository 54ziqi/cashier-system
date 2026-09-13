"""商家端：商品 API"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/merchant/products", tags=["merchant-products"])


# ── Pydantic schemas ─────────────────────────────────────────────

class SpecGroupBody(BaseModel):
    group_name: str
    required: bool = True
    min_select: int = 1
    max_select: int = 1


class SpecOptionBody(BaseModel):
    group_name: str
    value: str
    price_delta: int = 0


class SetSpecsBody(BaseModel):
    groups: list[SpecGroupBody]
    options: list[SpecOptionBody]


class Toggle86Body(BaseModel):
    is_86: bool


class BOMItem(BaseModel):
    material_id: str
    qty: float
    unit: str = "pcs"


class SetBOMBody(BaseModel):
    bom: list[BOMItem]


class ToggleComboBody(BaseModel):
    is_combo: bool


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
    return svc.list_products(
        page=page, page_size=page_size, status=status, category_id=category_id, q=q
    )


@router.get("/search")
async def search_products(
    request: Request,
    q: str = Query("", min_length=0),
    category_id: str = Query(""),
):
    user = await get_current_user(request)
    svc = _get_product_service(request)
    if category_id:
        return svc.list_products(page=1, page_size=200, category_id=category_id, q=q)[
            "items"
        ]
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
    result = svc.update_product(
        product_id, {k: v for k, v in data.model_dump().items() if v is not None}
    )
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


# ── M1 商品规格 API ─────────────────────────────────────────────


@router.post("/{product_id}/specs")
async def set_product_specs(request: Request, product_id: str, data: SetSpecsBody):
    """设置商品规格组与选项 (全量覆盖)"""
    await get_current_user(request)
    svc = _get_product_service(request)
    product = svc.get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    from app.infra.db.engine import session_factory
    from app.infra.db.models import ProductSpecGroup as GroupModel
    from app.infra.db.models import ProductSpecOption as OptionModel

    with session_factory() as s:
        s.query(GroupModel).filter_by(product_id=product_id).delete()
        s.query(OptionModel).filter_by(product_id=product_id).delete()

        groups = []
        for g in data.groups:
            gm = GroupModel(
                id=str(uuid.uuid4()),
                product_id=product_id,
                group_name=g.group_name,
                required=g.required,
                min_select=g.min_select,
                max_select=g.max_select,
            )
            s.add(gm)
            groups.append(gm)

        options = []
        for o in data.options:
            om = OptionModel(
                id=str(uuid.uuid4()),
                product_id=product_id,
                option_name=o.group_name,
                value=o.value,
                price_delta=o.price_delta,
            )
            s.add(om)
            options.append(om)

        s.commit()
        return {"id": product_id, "groups": len(groups), "options": len(options)}


@router.get("/{product_id}/specs")
async def get_product_specs(request: Request, product_id: str):
    """获取商品规格 (组 + 选项)"""
    await get_current_user(request)
    svc = _get_product_service(request)
    product = svc.get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    from app.infra.db.engine import session_factory
    from app.infra.db.models import ProductSpecGroup as GroupModel
    from app.infra.db.models import ProductSpecOption as OptionModel

    with session_factory() as s:
        groups = s.query(GroupModel).filter_by(product_id=product_id).all()
        options = s.query(OptionModel).filter_by(product_id=product_id).all()
        return {
            "groups": [
                {
                    "group_name": g.group_name,
                    "required": bool(g.required),
                    "min_select": g.min_select,
                    "max_select": g.max_select,
                }
                for g in groups
            ],
            "options": [
                {
                    "option_name": o.option_name,
                    "value": o.value,
                    "price_delta": o.price_delta,
                }
                for o in options
            ],
        }


# ── M1 86 沽清 API ──────────────────────────────────────────────


@router.post("/{product_id}/86")
async def toggle_86(request: Request, product_id: str, data: Toggle86Body):
    """商品沽清切换"""
    await get_current_user(request)
    product = _get_product_service(request).get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    from app.infra.db.engine import session_factory
    from app.infra.db.models import Product as ProductModel

    with session_factory() as s:
        p = s.query(ProductModel).filter_by(id=product_id, merchant_id="local").first()
        if not p:
            raise HTTPException(404, "商品不存在")
        p.is_86 = 1 if data.is_86 else 0
        s.commit()
        return {"id": product_id, "is_86": p.is_86}


@router.get("/86/list")
async def list_86_products(request: Request):
    """列出所有 86 商品"""
    await get_current_user(request)
    from app.infra.db.engine import session_factory
    from app.infra.db.models import Product as ProductModel

    with session_factory() as s:
        products = s.query(ProductModel).filter_by(merchant_id="local", is_86=1).all()
        return {"skus": [p.id for p in products]}


# ── M1 BOM 配方 API ─────────────────────────────────────────────


@router.post("/{product_id}/bom")
async def set_bom(request: Request, product_id: str, data: SetBOMBody):
    """设置商品原料配方 (bom_json)"""
    await get_current_user(request)
    product = _get_product_service(request).get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    import json

    from app.infra.db.engine import session_factory
    from app.infra.db.models import Product as ProductModel

    with session_factory() as s:
        p = s.query(ProductModel).filter_by(id=product_id, merchant_id="local").first()
        if not p:
            raise HTTPException(404, "商品不存在")
        p.bom_json = json.dumps([item.model_dump() for item in data.bom])
        s.commit()
        return {"id": product_id, "bom": data.bom}


# ── M4 套餐切换 API ─────────────────────────────────────────────


@router.post("/{product_id}/combo")
async def toggle_combo(request: Request, product_id: str, data: ToggleComboBody):
    """商品套餐切换"""
    await get_current_user(request)
    product = _get_product_service(request).get_product(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    from app.infra.db.engine import session_factory
    from app.infra.db.models import Product as ProductModel

    with session_factory() as s:
        p = s.query(ProductModel).filter_by(id=product_id, merchant_id="local").first()
        if not p:
            raise HTTPException(404, "商品不存在")
        p.is_combo = 1 if data.is_combo else 0
        s.commit()
        return {"id": product_id, "is_combo": p.is_combo}

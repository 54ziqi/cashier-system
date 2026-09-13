"""商家端：供应链/库存 ERP API (M4)"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.application.inventory.inventory_service import InventoryService
from app.application.inventory.physical_count_service import PhysicalCountService

router = APIRouter(prefix="/api/v1/merchant/inventory", tags=["merchant-inventory"])


# ── helpers ──────────────────────────────────────────────────

def _get_merchant_id(request: Request) -> str:
    tenant_id = getattr(request.app.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return "local"


def _inv_svc(request: Request) -> InventoryService:
    return InventoryService(merchant_id=_get_merchant_id(request))


def _pc_svc(request: Request) -> PhysicalCountService:
    return PhysicalCountService(merchant_id=_get_merchant_id(request))


# ── schemas ──────────────────────────────────────────────────

class WarehouseBody(BaseModel):
    name: str = "新仓库"
    type: str = "main"
    address: str = ""


class MaterialBody(BaseModel):
    name: str
    category: str = ""
    unit: str = "g"
    cost_price: int = 0
    stock: float = 0
    safety_stock: float = 0
    shelf_life_days: int | None = None


class InboundBody(BaseModel):
    warehouse_id: str
    material_id: str
    qty: float
    unit_price: int = 0
    operator_id: str = ""


class OutboundBody(BaseModel):
    warehouse_id: str
    material_id: str
    qty: float
    operator_id: str = ""


class TransferQuery(BaseModel):
    from_warehouse: str
    to_warehouse: str
    material_id: str
    qty: float
    operator_id: str = ""


class POItemBody(BaseModel):
    material_id: str
    qty_ordered: float
    unit_price: int = 0


class PurchaseOrderBody(BaseModel):
    items: list[POItemBody]
    supplier: str = ""
    note: str = ""


class SubmitLineBody(BaseModel):
    material_id: str
    counted_qty: float


# ── Warehouse ────────────────────────────────────────────────

@router.get("/warehouses")
async def list_warehouses(request: Request, user=Depends(get_current_user)):
    from app.infra.db.engine import session_factory
    from app.infra.db.models import Warehouse

    mid = _get_merchant_id(request)
    with session_factory() as s:
        rows = s.query(Warehouse).filter_by(merchant_id=mid).all()
        return {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "status": r.status,
                }
                for r in rows
            ]
        }


@router.post("/warehouses")
async def create_warehouse(request: Request, body: WarehouseBody, user=Depends(get_current_user)):
    svc = _inv_svc(request)
    wh = svc.init_warehouse(name=body.name)
    if body.type != "main":
        # 创建非主仓库
        import uuid
        from app.infra.db.engine import session_factory
        from app.infra.db.models import Warehouse as WarehouseModel

        with session_factory() as s:
            new_wh = WarehouseModel(
                id=str(uuid.uuid4()),
                merchant_id=svc.merchant_id,
                name=body.name,
                type=body.type,
                address=body.address,
            )
            s.add(new_wh)
            s.commit()
            s.refresh(new_wh)
            return {"id": new_wh.id, "name": new_wh.name}
    return {"id": wh.id, "name": wh.name}


# ── Materials ────────────────────────────────────────────────

@router.get("/materials")
async def list_materials(request: Request, user=Depends(get_current_user)):
    from app.infra.db.engine import session_factory
    from app.infra.db.models import Material

    mid = _get_merchant_id(request)
    with session_factory() as s:
        rows = (
            s.query(Material).filter_by(merchant_id=mid, status="active").all()
        )
        return {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "category": r.category,
                    "unit": r.unit,
                    "cost_price": r.cost_price,
                    "stock": r.stock,
                    "safety_stock": r.safety_stock,
                }
                for r in rows
            ]
        }


@router.post("/materials")
async def create_material(request: Request, body: MaterialBody, user=Depends(get_current_user)):
    import uuid
    from app.infra.db.engine import session_factory
    from app.infra.db.models import Material as MaterialModel

    mid = _get_merchant_id(request)
    with session_factory() as s:
        m = MaterialModel(
            id=str(uuid.uuid4()),
            merchant_id=mid,
            name=body.name,
            category=body.category,
            unit=body.unit,
            cost_price=body.cost_price,
            stock=body.stock,
            safety_stock=body.safety_stock,
            shelf_life_days=body.shelf_life_days,
        )
        s.add(m)
        s.commit()
        return {"id": m.id, "name": m.name}


# ── Stocks ───────────────────────────────────────────────────

@router.get("/stocks")
async def list_stocks(
    request: Request,
    warehouse_id: str = Query(""),
    low_stock: bool = Query(False),
    user=Depends(get_current_user),
):
    svc = _inv_svc(request)
    if warehouse_id or low_stock:
        items = svc.list_stocks(
            warehouse_id=warehouse_id,
            low_stock_only=low_stock,
        )
    else:
        items = svc.list_stocks(low_stock_only=low_stock)
    return {"items": items}


# ── Inbound / Outbound / Transfer ────────────────────────────

@router.post("/inbound")
async def inbound(request: Request, body: InboundBody, user=Depends(get_current_user)):
    svc = _inv_svc(request)
    try:
        mv = svc.inbound(
            warehouse_id=body.warehouse_id,
            material_id=body.material_id,
            qty=body.qty,
            unit_price=body.unit_price,
            operator_id=body.operator_id,
        )
        return {"movement_id": mv.id, "type": "inbound"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/outbound")
async def outbound(request: Request, body: OutboundBody, user=Depends(get_current_user)):
    svc = _inv_svc(request)
    try:
        mv = svc.outbound(
            warehouse_id=body.warehouse_id,
            material_id=body.material_id,
            qty=body.qty,
            operator_id=body.operator_id,
        )
        return {"movement_id": mv.id, "type": "outbound"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/transfer")
async def transfer(
    request: Request,
    from_wh: str = Query(...),
    to_wh: str = Query(...),
    material_id: str = Query(...),
    qty: float = Query(...),
    user=Depends(get_current_user),
):
    svc = _inv_svc(request)
    try:
        result = svc.transfer(from_wh, to_wh, material_id, qty)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Replenishment ────────────────────────────────────────────

@router.get("/replenishment")
async def replenishment(request: Request, user=Depends(get_current_user)):
    svc = _inv_svc(request)
    return {"items": svc.suggest_replenishment()}


# ── Purchase Orders ──────────────────────────────────────────

@router.get("/purchase-orders")
async def list_purchase_orders(
    request: Request,
    status: str = Query(""),
    user=Depends(get_current_user),
):
    svc = _inv_svc(request)
    return {"items": svc.list_purchase_orders(status_filter=status)}


@router.post("/purchase-orders")
async def create_purchase_order(
    request: Request,
    body: PurchaseOrderBody,
    user=Depends(get_current_user),
):
    svc = _inv_svc(request)
    items = [item.model_dump() for item in body.items]
    po = svc.create_purchase_order(
        items=items,
        supplier=body.supplier,
        operator_id=user.user_id,
        note=body.note,
    )
    return {"id": po.id, "status": po.status, "total_amount": po.total_amount}


@router.post("/purchase-orders/{po_id}/receive")
async def receive_purchase_order(
    request: Request,
    po_id: str,
    user=Depends(get_current_user),
):
    svc = _inv_svc(request)
    try:
        # 先审批再收货
        svc.approve_purchase_order(po_id, operator_id=user.user_id)
        result = svc.receive_po(po_id=po_id, operator_id=user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Physical Count ───────────────────────────────────────────

@router.get("/physical-counts")
async def list_physical_counts(
    request: Request,
    status: str = Query(""),
    user=Depends(get_current_user),
):
    svc = _pc_svc(request)
    return {"items": svc.list_sheets(status_filter=status)}


@router.post("/physical-counts")
async def create_physical_count(
    request: Request,
    warehouse_id: str = Query(...),
    user=Depends(get_current_user),
):
    svc = _pc_svc(request)
    try:
        sheet = svc.create_sheet(
            warehouse_id=warehouse_id,
            operator_id=user.user_id,
        )
        return {"id": sheet.id, "status": sheet.status}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/physical-counts/{sheet_id}/lines")
async def submit_physical_count_line(
    request: Request,
    sheet_id: str,
    body: SubmitLineBody,
    user=Depends(get_current_user),
):
    svc = _pc_svc(request)
    try:
        result = svc.submit_line(sheet_id, body.material_id, body.counted_qty)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/physical-counts/{sheet_id}/approve")
async def approve_physical_count(
    request: Request,
    sheet_id: str,
    user=Depends(get_current_user),
):
    svc = _pc_svc(request)
    try:
        result = svc.approve_sheet(sheet_id=sheet_id, operator_id=user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/physical-counts/{sheet_id}")
async def get_physical_count(request: Request, sheet_id: str, user=Depends(get_current_user)):
    svc = _pc_svc(request)
    result = svc.get_sheet(sheet_id)
    if not result:
        raise HTTPException(404, "盘点单不存在")
    return result

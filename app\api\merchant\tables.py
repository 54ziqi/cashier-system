"""商家端：桌台管理 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/merchant/tables", tags=["merchant-tables"])


class CreateTableBody(BaseModel):
    name: str
    capacity: int = 4
    pos_x: int = 0
    pos_y: int = 0
    sort_order: int = 0


class LayoutBody(BaseModel):
    name: str = ""
    capacity: int = 0
    pos_x: int = 0
    pos_y: int = 0
    sort_order: int = 0


class OccupyBody(BaseModel):
    order_id: str


def _get_table_service(request: Request):
    from app.application.table.table_service import TableService

    tenant_id = getattr(request.app.state, "tenant_id", None) or "local"
    merchant_id = getattr(request.app.state, "merchant_id", None) or tenant_id
    return TableService(merchant_id=merchant_id)


@router.get("")
async def list_tables(request: Request, status: str = ""):
    await get_current_user(request)
    svc = _get_table_service(request)
    tables = svc.list_tables(status=status)
    return {"items": tables, "total": len(tables)}


@router.post("")
async def create_table(request: Request, data: CreateTableBody):
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        return svc.create_table(
            name=data.name,
            capacity=data.capacity,
            pos_x=data.pos_x,
            pos_y=data.pos_y,
            sort_order=data.sort_order,
        )
    except TableError as e:
        raise HTTPException(400, str(e))


@router.post("/{table_id}/seat")
async def seat_table(request: Request, table_id: str):
    """开台（empty → seated）"""
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        return svc.seat(table_id)
    except TableError as e:
        raise HTTPException(400, str(e))


@router.post("/{table_id}/clear")
async def clear_table(request: Request, table_id: str):
    """清台（seated/dirty → empty）"""
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        return svc.clear_table(table_id)
    except TableError as e:
        raise HTTPException(400, str(e))


@router.post("/{table_id}/reserve")
async def reserve_table(request: Request, table_id: str):
    """预留（empty → reserved）"""
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        return svc.reserve(table_id)
    except TableError as e:
        raise HTTPException(400, str(e))


@router.post("/{table_id}/occupy")
async def occupy_table(request: Request, table_id: str, body: OccupyBody):
    """绑定订单到桌台"""
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        svc.occupy(table_id, body.order_id)
        return {"ok": True, "table_id": table_id, "order_id": body.order_id}
    except TableError as e:
        raise HTTPException(400, str(e))


@router.put("/{table_id}/layout")
async def update_layout(request: Request, table_id: str, body: LayoutBody):
    """更新桌台位置/属性"""
    await get_current_user(request)
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        return svc.update_layout(
            table_id,
            name=body.name,
            capacity=body.capacity,
            pos_x=body.pos_x,
            pos_y=body.pos_y,
            sort_order=body.sort_order,
        )
    except TableError as e:
        raise HTTPException(400, str(e))


@router.delete("/{table_id}")
async def delete_table(request: Request, table_id: str, user=Depends(require_admin)):
    """删除桌台（需 admin 权限）"""
    svc = _get_table_service(request)
    from app.application.table.table_service import TableError

    try:
        svc.delete_table(table_id)
        return {"deleted": True, "id": table_id}
    except TableError as e:
        raise HTTPException(400, str(e))

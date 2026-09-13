"""M6 应用层：门店间库存调拨服务"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.application.inventory.inventory_service import InventoryService
from app.infra.db.engine import session_factory
from app.infra.db.models import TransferOrder as TransferOrderModel
from app.infra.db.models import (
    TransferOrderItem as TransferOrderItemModel,
)
from app.infra.db.models import (
    Warehouse as WarehouseModel,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TransferService:
    """门店间库存调拨服务：创建 / 发货 / 收货 / 作废 / 查询"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── CRUD ────────────────────────────────────────────────

    def create(
        self,
        from_warehouse_id: str,
        to_warehouse_id: str,
        items: list[dict],
        operator_id: str = "",
    ) -> dict:
        """创建调拨单 (CAS 校验仓库归属)"""
        if not items:
            raise ValueError("调拨明细不能为空")
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("调出仓库与调入仓库不能相同")

        with session_factory() as s:
            # 校验两个仓库同属本商户
            wh_from = (
                s.query(WarehouseModel)
                .filter_by(id=from_warehouse_id, merchant_id=self.merchant_id)
                .first()
            )
            wh_to = (
                s.query(WarehouseModel)
                .filter_by(id=to_warehouse_id, merchant_id=self.merchant_id)
                .first()
            )
            if not wh_from:
                raise ValueError(f"调出仓库不存在: {from_warehouse_id}")
            if not wh_to:
                raise ValueError(f"调入仓库不存在: {to_warehouse_id}")

            transfer = TransferOrderModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                from_warehouse_id=from_warehouse_id,
                to_warehouse_id=to_warehouse_id,
                status="draft",
                operator_id=operator_id or None,
            )
            s.add(transfer)

            total_qty = 0.0
            for it in items:
                qty = float(it["qty"])
                if qty <= 0:
                    raise ValueError(f"调拨数量必须为正: {it}")

                item = TransferOrderItemModel(
                    id=str(uuid.uuid4()),
                    transfer_id=transfer.id,
                    material_id=it["material_id"],
                    qty=qty,
                    unit_cost=int(it.get("unit_cost", 0)),
                    subtotal=int(qty * int(it.get("unit_cost", 0))),
                )
                s.add(item)
                total_qty += qty

            transfer.total_qty = total_qty
            s.commit()
            s.refresh(transfer)
            created_items = (
                s.query(TransferOrderItemModel)
                .filter_by(transfer_id=transfer.id)
                .all()
            )
            return self._to_dict(transfer, items=created_items)

    def ship(self, transfer_id: str, operator_id: str = "") -> dict:
        """发货：draft → CAS → shipping，并出库源仓库"""
        transfer = None
        items = None
        with session_factory() as s:
            # CAS 更新状态
            result = s.execute(
                text(
                    "UPDATE transfer_orders SET status='shipping', "
                    "operator_id=:op, shipped_at=:ts, updated_at=:ts "
                    "WHERE id=:id AND status='draft'"
                ),
                {
                    "id": transfer_id,
                    "op": operator_id or None,
                    "ts": _utcnow(),
                },
            )
            if result.rowcount == 0:
                existing = (
                    s.query(TransferOrderModel).filter_by(id=transfer_id).first()
                )
                if not existing:
                    raise ValueError(f"调拨单不存在: {transfer_id}")
                raise ValueError(
                    f"调拨单状态不可发货: {existing.status} (期望 draft)"
                )

            # 读取出库明细 + transfer
            items = (
                s.query(TransferOrderItemModel)
                .filter_by(transfer_id=transfer_id)
                .all()
            )
            transfer = (
                s.query(TransferOrderModel).filter_by(id=transfer_id).first()
            )
            s.commit()

        # 独立会话做库存操作
        inv = InventoryService(self.merchant_id)
        for item in items:
            inv.outbound(
                warehouse_id=transfer.from_warehouse_id,
                material_id=item.material_id,
                qty=item.qty,
                ref_table="transfer_orders",
                ref_id=transfer_id,
                operator_id=operator_id,
            )

        return self._to_dict(transfer)

    def receive(self, transfer_id: str, operator_id: str = "") -> dict:
        """收货：shipping → CAS → received，并入库目标仓库"""
        transfer = None
        items = None
        with session_factory() as s:
            result = s.execute(
                text(
                    "UPDATE transfer_orders SET status='received', "
                    "operator_id=:op, received_at=:ts, updated_at=:ts "
                    "WHERE id=:id AND status='shipping'"
                ),
                {
                    "id": transfer_id,
                    "op": operator_id or None,
                    "ts": _utcnow(),
                },
            )
            if result.rowcount == 0:
                existing = (
                    s.query(TransferOrderModel).filter_by(id=transfer_id).first()
                )
                if not existing:
                    raise ValueError(f"调拨单不存在: {transfer_id}")
                raise ValueError(
                    f"调拨单状态不可收货: {existing.status} (期望 shipping)"
                )

            items = (
                s.query(TransferOrderItemModel)
                .filter_by(transfer_id=transfer_id)
                .all()
            )
            transfer = (
                s.query(TransferOrderModel).filter_by(id=transfer_id).first()
            )
            s.commit()

        # 独立会话做库存操作
        inv = InventoryService(self.merchant_id)
        for item in items:
            inv.inbound(
                warehouse_id=transfer.to_warehouse_id,
                material_id=item.material_id,
                qty=item.qty,
                ref_table="transfer_orders",
                ref_id=transfer_id,
                operator_id=operator_id,
            )

        return self._to_dict(transfer)

    def void(self, transfer_id: str, operator_id: str = "") -> dict:
        """作废：仅 draft 状态可废"""
        with session_factory() as s:
            result = s.execute(
                text(
                    "UPDATE transfer_orders SET status='void', "
                    "operator_id=:op, updated_at=:ts "
                    "WHERE id=:id AND status='draft'"
                ),
                {
                    "id": transfer_id,
                    "op": operator_id or None,
                    "ts": _utcnow(),
                },
            )
            if result.rowcount == 0:
                existing = (
                    s.query(TransferOrderModel).filter_by(id=transfer_id).first()
                )
                if not existing:
                    raise ValueError(f"调拨单不存在: {transfer_id}")
                raise ValueError(
                    f"调拨单状态不可作废: {existing.status} (期望 draft)"
                )

            s.commit()
            transfer = (
                s.query(TransferOrderModel).filter_by(id=transfer_id).first()
            )
            return self._to_dict(transfer)

    def get_transfer(self, id: str) -> dict:
        """获取单个调拨单"""
        with session_factory() as s:
            t = s.query(TransferOrderModel).filter_by(id=id).first()
            if not t:
                raise ValueError(f"调拨单不存在: {id}")
            items = s.query(TransferOrderItemModel).filter_by(transfer_id=id).all()
            return self._to_dict(t, items=items)

    def list_transfers(self, status: str = "") -> list[dict]:
        """列出当前商户的调拨单"""
        with session_factory() as s:
            q = s.query(TransferOrderModel).filter_by(
                merchant_id=self.merchant_id
            )
            if status:
                q = q.filter_by(status=status)
            rows = q.order_by(TransferOrderModel.created_at.desc()).all()
            return [self._to_dict(t) for t in rows]

    # ── 内联序列化 ─────────────────────────────────────────

    def _to_dict(
        self,
        t: TransferOrderModel,
        items: list | None = None,
    ) -> dict:
        d = {
            "id": t.id,
            "merchant_id": t.merchant_id,
            "from_warehouse_id": t.from_warehouse_id,
            "to_warehouse_id": t.to_warehouse_id,
            "status": t.status,
            "total_qty": t.total_qty,
            "operator_id": t.operator_id or "",
            "freight_cost": t.freight_cost,
            "note": t.note or "",
            "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        if items is not None:
            d["items"] = [
                {
                    "id": it.id,
                    "material_id": it.material_id,
                    "qty": it.qty,
                    "unit_cost": it.unit_cost,
                    "subtotal": it.subtotal,
                }
                for it in items
            ]
        return d

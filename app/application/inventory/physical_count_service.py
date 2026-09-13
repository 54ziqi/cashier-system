"""应用层：盘点服务 - 创建盘点单/录入盘点数/审批生成差异入账"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    Material as MaterialModel,
    PhysicalInventoryLine as PILModel,
    PhysicalInventorySheet as PISModel,
    StockMovement as StockMovementModel,
    Warehouse as WarehouseModel,
    WarehouseStock as WSModel,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PhysicalCountService:
    """盘点服务：创建盘点单 → 录入盘点数 → 审批生成差异入账"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def create_sheet(self, warehouse_id: str, operator_id: str = "") -> PISModel:
        """创建盘点单：自动从 warehouse_stocks 生成明细行（book_qty=当前库存）"""
        with session_factory() as s:
            wh = (
                s.query(WarehouseModel)
                .filter_by(id=warehouse_id, merchant_id=self.merchant_id)
                .first()
            )
            if not wh:
                raise ValueError(f"仓库不存在: {warehouse_id}")

            sheet = PISModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                warehouse_id=warehouse_id,
                status="draft",
                operator_id=operator_id,
            )
            s.add(sheet)

            # 自动填充明细行
            ws_rows = s.query(WSModel).filter_by(warehouse_id=warehouse_id).all()
            for ws in ws_rows:
                line = PILModel(
                    id=str(uuid.uuid4()),
                    sheet_id=sheet.id,
                    material_id=ws.material_id,
                    book_qty=ws.qty,
                    counted_qty=ws.qty,  # 默认等于账面
                    variance=0,
                )
                s.add(line)

            s.commit()
            s.refresh(sheet)
            return sheet

    def submit_line(self, sheet_id: str, material_id: str, counted_qty: float) -> dict:
        """录入/更新某一行的盘点数量"""
        with session_factory() as s:
            line = (
                s.query(PILModel)
                .filter_by(sheet_id=sheet_id, material_id=material_id)
                .first()
            )
            if not line:
                raise ValueError(f"盘点行不存在: sheet={sheet_id} material={material_id}")

            sheet = (
                s.query(PISModel).filter_by(id=sheet_id, merchant_id=self.merchant_id).first()
            )
            if not sheet or sheet.status not in ("draft", "counting"):
                raise ValueError(f"盘点单状态不可录入: {sheet.status if sheet else 'not found'}")

            # 查 unit_cost (原料当前单位成本)
            mat = (
                s.query(MaterialModel)
                .filter_by(id=material_id, merchant_id=self.merchant_id)
                .first()
            )
            unit_cost = mat.cost_price if mat else 0

            line.counted_qty = counted_qty
            line.variance = counted_qty - line.book_qty
            line.unit_cost = unit_cost
            line.variance_amount = int(line.variance * unit_cost)

            # 如果所有行都已盘点进入 counting 状态
            if sheet.status == "draft":
                sheet.status = "counting"

            s.commit()
            return {
                "sheet_id": sheet_id,
                "material_id": material_id,
                "book_qty": line.book_qty,
                "counted_qty": counted_qty,
                "variance": line.variance,
                "variance_amount": line.variance_amount,
            }

    def approve_sheet(self, sheet_id: str, operator_id: str = "") -> dict:
        """审批盘点单：用差异更新库存 + 写流水 + 更新 sheet.total_variance"""
        with session_factory() as s:
            sheet = (
                s.query(PISModel)
                .filter_by(id=sheet_id, merchant_id=self.merchant_id)
                .first()
            )
            if not sheet:
                raise ValueError(f"盘点单不存在: {sheet_id}")
            if sheet.status not in ("draft", "counting"):
                raise ValueError(f"盘点单不可审批，状态: {sheet.status}")

            lines = s.query(PILModel).filter_by(sheet_id=sheet_id).all()
            total_variance = 0
            adjust_count = 0

            for line in lines:
                if line.variance == 0:
                    continue

                # 更新仓库库存
                s.execute(
                    text(
                        "UPDATE warehouse_stocks SET qty = qty + :delta "
                        "WHERE warehouse_id = :wid AND material_id = :mid"
                    ),
                    {
                        "delta": line.variance,
                        "wid": sheet.warehouse_id,
                        "mid": line.material_id,
                    },
                )
                # 更新原料总库存
                s.execute(
                    text(
                        "UPDATE materials SET stock = stock + :delta, updated_at = :now "
                        "WHERE id = :mid"
                    ),
                    {
                        "delta": line.variance,
                        "now": _utcnow().isoformat(),
                        "mid": line.material_id,
                    },
                )

                # 读取 adjusted qty
                bal_row = s.execute(
                    text(
                        "SELECT qty FROM warehouse_stocks "
                        "WHERE warehouse_id = :wid AND material_id = :mid"
                    ),
                    {"wid": sheet.warehouse_id, "mid": line.material_id},
                ).fetchone()
                balance_after = float(bal_row[0]) if bal_row else 0

                # 流水记录
                mv = StockMovementModel(
                    id=str(uuid.uuid4()),
                    warehouse_id=sheet.warehouse_id,
                    material_id=line.material_id,
                    type="adjust",
                    qty=line.variance,
                    balance_after=balance_after,
                    ref_table="adjust",
                    ref_id=sheet_id,
                    operator_id=operator_id,
                    note=f"盘点调整: {line.material_id}",
                )
                s.add(mv)
                total_variance += line.variance_amount
                adjust_count += 1

            sheet.status = "approved"
            sheet.approved_at = _utcnow()
            sheet.total_variance = total_variance
            sheet.updated_at = _utcnow()
            s.commit()

            return {
                "sheet_id": sheet_id,
                "status": "approved",
                "total_variance": total_variance,
                "adjust_count": adjust_count,
            }

    def get_sheet(self, sheet_id: str) -> dict | None:
        """获取盘点单详情（含明细行）"""
        with session_factory() as s:
            sheet = (
                s.query(PISModel)
                .filter_by(id=sheet_id, merchant_id=self.merchant_id)
                .first()
            )
            if not sheet:
                return None
            lines = s.query(PILModel).filter_by(sheet_id=sheet_id).all()
            return {
                "id": sheet.id,
                "merchant_id": sheet.merchant_id,
                "warehouse_id": sheet.warehouse_id,
                "status": sheet.status,
                "total_variance": sheet.total_variance,
                "operator_id": sheet.operator_id,
                "created_at": sheet.created_at.isoformat() if sheet.created_at else "",
                "approved_at": sheet.approved_at.isoformat() if sheet.approved_at else "",
                "lines": [
                    {
                        "id": ln.id,
                        "material_id": ln.material_id,
                        "book_qty": ln.book_qty,
                        "counted_qty": ln.counted_qty,
                        "variance": ln.variance,
                        "unit_cost": ln.unit_cost,
                        "variance_amount": ln.variance_amount,
                    }
                    for ln in lines
                ],
            }

    def list_sheets(self, status_filter: str = "") -> list[dict]:
        """列出盘点单"""
        with session_factory() as s:
            query = s.query(PISModel).filter_by(merchant_id=self.merchant_id)
            if status_filter:
                query = query.filter_by(status=status_filter)
            rows = query.order_by(PISModel.created_at.desc()).all()
            return [
                {
                    "id": r.id,
                    "warehouse_id": r.warehouse_id,
                    "status": r.status,
                    "total_variance": r.total_variance,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

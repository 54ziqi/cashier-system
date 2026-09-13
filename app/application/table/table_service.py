"""应用层：桌台服务 - 桌台 CRUD + 状态流转"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.infra.db.engine import session_factory
from app.infra.db.models import DiningTable as DiningTableModel

log = logging.getLogger(__name__)


class TableError(Exception):
    pass


class TableService:
    """桌台管理服务"""

    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    # ── CRUD ────────────────────────────────────────────────────

    def create_defaults(self) -> None:
        """初始化默认桌台 A01..A10"""
        with session_factory() as s:
            existing = (
                s.query(DiningTableModel)
                .filter_by(merchant_id=self.merchant_id)
                .count()
            )
            if existing > 0:
                return
            for i in range(1, 11):
                table = DiningTableModel(
                    id=str(uuid.uuid4()),
                    merchant_id=self.merchant_id,
                    name=f"A{i:02d}",
                    capacity=4,
                    status="empty",
                    sort_order=i,
                )
                s.add(table)
            s.commit()

    def list_tables(self, status: str = "") -> list[dict]:
        with session_factory() as s:
            q = s.query(DiningTableModel).filter_by(merchant_id=self.merchant_id)
            if status:
                q = q.filter_by(status=status)
            tables = q.order_by(DiningTableModel.sort_order).all()
            return [
                {
                    "id": t.id,
                    "merchant_id": t.merchant_id,
                    "name": t.name,
                    "capacity": t.capacity,
                    "status": t.status,
                    "current_order_id": t.current_order_id,
                    "pos_x": t.pos_x,
                    "pos_y": t.pos_y,
                    "sort_order": t.sort_order,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                    "updated_at": t.updated_at.isoformat() if t.updated_at else "",
                }
                for t in tables
            ]

    def get_table(self, table_id: str) -> DiningTableModel | None:
        with session_factory() as s:
            t = s.query(DiningTableModel).filter_by(
                id=table_id, merchant_id=self.merchant_id
            ).first()
            return t

    def create_table(
        self,
        name: str,
        capacity: int = 4,
        pos_x: int = 0,
        pos_y: int = 0,
        sort_order: int = 0,
    ) -> dict:
        with session_factory() as s:
            # 检查同名
            dup = (
                s.query(DiningTableModel)
                .filter_by(merchant_id=self.merchant_id, name=name)
                .first()
            )
            if dup:
                raise TableError(f"桌台名称已存在: {name}")
            table = DiningTableModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=name,
                capacity=capacity,
                status="empty",
                pos_x=pos_x,
                pos_y=pos_y,
                sort_order=sort_order,
            )
            s.add(table)
            s.commit()
            return self._to_dict(table)

    def delete_table(self, table_id: str) -> None:
        with session_factory() as s:
            table = (
                s.query(DiningTableModel)
                .filter_by(id=table_id, merchant_id=self.merchant_id)
                .first()
            )
            if not table:
                raise TableError("桌台不存在")
            if table.status not in ("empty", "disabled"):
                raise TableError(f"无法删除状态为 {table.status} 的桌台")
            s.delete(table)
            s.commit()

    # ── 状态流转 ────────────────────────────────────────────────

    def seat(self, table_id: str) -> dict:
        """开台：empty → seated"""
        return self._cas_transition(
            table_id, from_status="empty", to_status="seated", action="seat"
        )

    def clear_table(self, table_id: str) -> dict:
        """清台：seated/dirty → empty (同时解除 current_order_id)"""
        with session_factory() as s:
            table = self._get_or_404(s, table_id)
            if table.status not in ("seated", "dirty"):
                raise TableError(f"无法清理状态为 {table.status} 的桌台")
            result = s.execute(
                text(
                    "UPDATE dining_tables SET status = 'empty', "
                    "current_order_id = NULL, updated_at = :now "
                    "WHERE id = :tid AND status IN ('seated', 'dirty')"
                ),
                {"now": _utcnow().isoformat(), "tid": table_id},
            )
            if result.rowcount == 0:
                raise TableError("CAS 冲突：桌台状态已变更")
            s.commit()
            return self._to_dict(table, refresh_status="empty")

    def occupy(self, table_id: str, order_id: str) -> None:
        """绑定订单：seated + current_order_id"""
        with session_factory() as s:
            table = self._get_or_404(s, table_id)
            if table.status != "seated":
                raise TableError(f"桌台 {table.name} 未开台，无法绑定订单")
            table.current_order_id = order_id
            table.updated_at = _utcnow()
            s.commit()

    def vacate(self, table_id: str) -> None:
        """解除绑定：current_order_id → null"""
        with session_factory() as s:
            table = self._get_or_404(s, table_id)
            table.current_order_id = None
            table.updated_at = _utcnow()
            s.commit()

    def reserve(self, table_id: str) -> dict:
        """预留：empty → reserved"""
        return self._cas_transition(
            table_id, from_status="empty", to_status="reserved", action="reserve"
        )

    def update_layout(
        self,
        table_id: str,
        name: str = "",
        capacity: int = 0,
        pos_x: int = 0,
        pos_y: int = 0,
        sort_order: int = 0,
    ) -> dict:
        """更新位置/属性"""
        with session_factory() as s:
            table = self._get_or_404(s, table_id)
            if name:
                # 检查同名冲突（排除自己）
                dup = (
                    s.query(DiningTableModel)
                    .filter(
                        DiningTableModel.merchant_id == self.merchant_id,
                        DiningTableModel.name == name,
                        DiningTableModel.id != table_id,
                    )
                    .first()
                )
                if dup:
                    raise TableError(f"桌台名称已存在: {name}")
                table.name = name
            if capacity > 0:
                table.capacity = capacity
            table.pos_x = pos_x
            table.pos_y = pos_y
            table.sort_order = sort_order
            table.updated_at = _utcnow()
            s.commit()
            return self._to_dict(table)

    # ── internal ─────────────────────────────────────────────────

    def _cas_transition(
        self, table_id: str, from_status: str, to_status: str, action: str
    ) -> dict:
        with session_factory() as s:
            table = self._get_or_404(s, table_id)
            if table.status != from_status:
                raise TableError(
                    f"Cannot {action}: expected status '{from_status}', "
                    f"got '{table.status}'"
                )
            result = s.execute(
                text(
                    "UPDATE dining_tables SET status = :ts, "
                    "updated_at = :now WHERE id = :tid AND status = :fs"
                ),
                {
                    "ts": to_status,
                    "now": _utcnow().isoformat(),
                    "tid": table_id,
                    "fs": from_status,
                },
            )
            if result.rowcount == 0:
                raise TableError("CAS 冲突：桌台状态已变更")
            s.commit()
            return self._to_dict(table, refresh_status=to_status)

    def _get_or_404(self, s, table_id: str) -> DiningTableModel:
        table = (
            s.query(DiningTableModel)
            .filter_by(id=table_id, merchant_id=self.merchant_id)
            .first()
        )
        if not table:
            raise TableError("桌台不存在")
        return table

    def _to_dict(self, table: DiningTableModel, refresh_status: str = "") -> dict:
        status = refresh_status or table.status
        return {
            "id": table.id,
            "merchant_id": table.merchant_id,
            "name": table.name,
            "capacity": table.capacity,
            "status": status,
            "current_order_id": table.current_order_id,
            "pos_x": table.pos_x,
            "pos_y": table.pos_y,
            "sort_order": table.sort_order,
            "created_at": table.created_at.isoformat() if table.created_at else "",
            "updated_at": table.updated_at.isoformat() if table.updated_at else "",
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

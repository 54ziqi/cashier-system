"""应用层：KDS 厨房制作单服务 - 订单流转到后厨"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    KdsTicket as KdsTicketModel,
    Order as OrderModel,
    OrderItem as OrderItemModel,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KdsService:
    """厨房制作单服务"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── 创建制作单 ──────────────────────────────────────────

    def create_tickets(self, order_id: str) -> list[KdsTicketModel]:
        """订单 paid 时创建 KDS 制作单"""
        with session_factory() as s:
            order = s.query(OrderModel).filter_by(id=order_id).first()
            if not order:
                log.warning(f"KDS: 订单不存在 {order_id}")
                return []

            items = s.query(OrderItemModel).filter_by(order_id=order_id).all()
            tickets = []
            for item in items:
                station = _infer_station(item.product_name)
                ticket = KdsTicketModel(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    merchant_id=self.merchant_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    spec_text=item.spec_text,
                    table_name=order.table_name,
                    status="pending",
                    kds_station=station,
                )
                s.add(ticket)
                tickets.append(ticket)

            s.commit()
            log.info(f"KDS: 为订单 {order_id} 创建了 {len(tickets)} 个制作单")
            return tickets

    # ── 状态流转 ────────────────────────────────────────────

    def mark_cooking(self, ticket_id: str) -> dict:
        """pending → cooking"""
        return self._transition(ticket_id, "cooking", "start_at")

    def mark_ready(self, ticket_id: str) -> dict:
        """cooking → ready"""
        return self._transition(ticket_id, "ready", "done_at")

    def mark_served(self, ticket_id: str) -> dict:
        """ready → served"""
        return self._transition(ticket_id, "served", "")

    def mark_void(self, ticket_id: str) -> dict:
        """任意非终态 → void"""
        return self._transition(ticket_id, "void", "")

    def fire_ticket(self, ticket_id: str) -> dict:
        """叫起：标记 fire_at = now"""
        with session_factory() as s:
            ticket = s.query(KdsTicketModel).filter_by(id=ticket_id).first()
            if not ticket:
                raise ValueError(f"KDS 制作单不存在: {ticket_id}")
            ticket.fire_at = _utcnow()
            ticket.updated_at = _utcnow()
            s.commit()
            return {"ticket_id": ticket_id, "fired": True, "fire_at": ticket.fire_at.isoformat()}

    # ── 查询 ────────────────────────────────────────────────

    def get_queue(self, station: str = "") -> list[dict]:
        """获取待制作列表（按 station 筛选）"""
        with session_factory() as s:
            query = s.query(KdsTicketModel).filter(
                KdsTicketModel.merchant_id == self.merchant_id,
                KdsTicketModel.status.in_(["pending", "cooking", "ready"]),
            )
            if station:
                query = query.filter(KdsTicketModel.kds_station == station)
            rows = query.order_by(KdsTicketModel.created_at.asc()).all()
            return [self._to_dict(r) for r in rows]

    def get_order_tickets(self, order_id: str) -> list[dict]:
        """获取某订单的所有制作单"""
        with session_factory() as s:
            rows = (
                s.query(KdsTicketModel)
                .filter_by(order_id=order_id, merchant_id=self.merchant_id)
                .order_by(KdsTicketModel.created_at.asc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    # ── 内部 ────────────────────────────────────────────────

    def _transition(self, ticket_id: str, to_status: str, time_field: str = "") -> dict:
        with session_factory() as s:
            ticket = s.query(KdsTicketModel).filter_by(id=ticket_id).first()
            if not ticket:
                raise ValueError(f"KDS 制作单不存在: {ticket_id}")
            from_status = ticket.status
            ticket.status = to_status
            if time_field:
                setattr(ticket, time_field, _utcnow())
            ticket.updated_at = _utcnow()
            s.commit()
            return {
                "ticket_id": ticket_id,
                "from_status": from_status,
                "to_status": to_status,
            }

    def _to_dict(self, r) -> dict:
        return {
            "id": r.id,
            "order_id": r.order_id,
            "product_name": r.product_name,
            "quantity": r.quantity,
            "spec_text": r.spec_text,
            "table_name": r.table_name,
            "status": r.status,
            "urgent": r.urgent,
            "fire_at": r.fire_at.isoformat() if r.fire_at else "",
            "start_at": r.start_at.isoformat() if r.start_at else "",
            "done_at": r.done_at.isoformat() if r.done_at else "",
            "kds_station": r.kds_station,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }


def _infer_station(product_name: str) -> str:
    """根据商品名推断出品档口"""
    cold_keywords = ["凉", "冷", "拌", "冰"]
    drink_keywords = ["饮", "茶", "咖啡", "可乐", "水", "奶"]
    grill_keywords = ["烤", "烧", "炸"]

    for kw in cold_keywords:
        if kw in product_name:
            return "凉菜"
    for kw in drink_keywords:
        if kw in product_name:
            return "饮品"
    for kw in grill_keywords:
        if kw in product_name:
            return "烧烤"
    return "烹调"

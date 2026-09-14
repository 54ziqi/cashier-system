"""应用层：ESC/POS 打印服务 - 构建打印任务/队列/模拟打印"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    EscPosJob as EscPosJobModel,
)

log = logging.getLogger(__name__)

# ── ESC/POS 模板名称常量 ──────────────────────────────────

ESC_POS_TMPL_RECEIPT = "receipt"
ESC_POS_TMPL_LABEL = "label"
ESC_POS_TMPL_KDS = "kds"
ESC_POS_TMPL_REPORT = "report"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EscPosService:
    """ESC/POS 打印任务管理"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── 构建打印数据 ────────────────────────────────────────

    def build_receipt(self, order_data: dict) -> bytes:
        """构建小票 ESC/POS 字节流"""
        lines = [
            b"\x1b\x40",  # 初始化
            b"\x1b\x61\x01",  # 居中
            "柒号收银\n".encode("gbk", errors="replace"),
            b"\x1b\x61\x00",  # 左对齐
            b"----------------------------------------\n",
            f"订单号: {order_data.get('order_no', '')}\n".encode("gbk", errors="replace"),
            f"时间: {order_data.get('created_at', '')}\n".encode("gbk", errors="replace"),
            b"----------------------------------------\n",
        ]
        for item in order_data.get("items", []):
            name = item.get("product_name", "")[:16]
            qty = item.get("quantity", 1)
            price = item.get("subtotal", 0)
            line = f"{name} x{qty} {price / 100:.2f}\n"
            lines.append(line.encode("gbk", errors="replace"))

        lines.extend([
            b"----------------------------------------\n",
            f"合计: {order_data.get('final_amount', 0) / 100:.2f} 元\n".encode("gbk", errors="replace"),
            b"\n\n\n\x1d\x56\x01",  # 切纸
        ])
        return b"".join(lines)

    def build_label(self, order_item_data: dict) -> bytes:
        """构建标签打印字节流"""
        lines = [
            b"\x1b\x40",  # 初始化
            b"\x1b\x61\x01",  # 居中
            f"{order_item_data.get('product_name', '')}\n".encode("gbk", errors="replace"),
            f"{order_item_data.get('spec_text', '')}\n".encode("gbk", errors="replace"),
            b"\n\n\x1d\x56\x01",  # 切纸
        ]
        return b"".join(lines)

    def build_kds(self, ticket_data: dict) -> bytes:
        """构建 KDS 叫制单打印字节流"""
        lines = [
            b"\x1b\x40",
            b"\x1b\x61\x01",  # 居中
            b"=== KDS ===\n",
            b"\x1b\x61\x00",
            f"桌台: {ticket_data.get('table_name', '')}\n".encode("gbk", errors="replace"),
            f"商品: {ticket_data.get('product_name', '')}\n".encode("gbk", errors="replace"),
            f"数量: {ticket_data.get('quantity', 1)}\n".encode("gbk", errors="replace"),
            f"备注: {ticket_data.get('spec_text', '')}\n".encode("gbk", errors="replace"),
            b"\n\n",
        ]
        return b"".join(lines)

    # ── 打印队列管理 ────────────────────────────────────────

    def enqueue(self, job_type: str, target: str, payload: dict | bytes) -> EscPosJobModel:
        """将打印任务入队"""
        import json
        payload_json = (
            payload.decode("latin-1")
            if isinstance(payload, bytes)
            else json.dumps(payload, ensure_ascii=False)
        )
        with session_factory() as s:
            job = EscPosJobModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                job_type=job_type,
                target=target,
                payload_json=payload_json,
                status="pending",
            )
            s.add(job)
            s.commit()
            s.refresh(job)
            return job

    def process_queue(self) -> list[dict]:
        """轮询 pending jobs 并模拟完成（单机版 stub）"""
        import json
        results = []
        with session_factory() as s:
            pending_jobs = (
                s.query(EscPosJobModel)
                .filter_by(merchant_id=self.merchant_id, status="pending")
                .order_by(EscPosJobModel.created_at.asc())
                .limit(10)
                .all()
            )
            for job in pending_jobs:
                try:
                    # 模拟打印成功
                    job.status = "done"
                    job.updated_at = _utcnow()
                    results.append({"job_id": job.id, "status": "done"})
                    log.info(f"打印完成: {job.job_type} -> {job.target}")
                except Exception as e:
                    job.status = "failed"
                    job.error_msg = str(e)
                    job.updated_at = _utcnow()
                    results.append({"job_id": job.id, "status": "failed", "error": str(e)})
            s.commit()
        return results

    def print_test(self, target: str = "default") -> EscPosJobModel:
        """打印测试页"""
        test_payload = {
            "type": "test",
            "content": "柒号收银 - 打印测试页\n如果看到这行字，说明打印机正常。\n",
        }
        return self.enqueue("receipt", target, test_payload)

    def list_jobs(self, status_filter: str = "") -> list[dict]:
        """列出打印任务"""
        with session_factory() as s:
            query = s.query(EscPosJobModel).filter_by(merchant_id=self.merchant_id)
            if status_filter:
                query = query.filter_by(status=status_filter)
            rows = query.order_by(EscPosJobModel.created_at.desc()).limit(50).all()
            return [
                {
                    "id": r.id,
                    "job_type": r.job_type,
                    "target": r.target,
                    "status": r.status,
                    "error_msg": r.error_msg,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

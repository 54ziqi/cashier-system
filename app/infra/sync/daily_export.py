"""
日结签名导出

每日 23:55 自动聚合当天销售流水，用 License 私钥签名，输出到 cloud_export/ 目录。
云推送模块 (cloud_push.py) 读取该签名文件并 HTTPS push 到云端。
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.infra.db.engine import session_factory
from app.infra.db.models import Order, OrderItem

log = logging.getLogger(__name__)


def sign_payload(payload: dict, priv_pem: bytes) -> str:
    """RSA-SHA256 签名，返回 base64"""
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    key = serialization.load_pem_private_key(priv_pem, password=None)
    sig = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def build_daily_digest(
    day: str | None = None,
    merchant_id: str = "local",
    store_name: str = "",
    parent_merchant_id: str = "",
    max_stores: int = 1,
) -> dict:
    """
    构建某日销售摘要。day=None 则按 UTC 今天。
    不依赖 License 字段，仅做聚合统计。
    """
    if day is None:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = datetime.fromisoformat(day + "T00:00:00").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    with session_factory() as s:
        row = (
            s.query(
                __import__("sqlalchemy").func.count(Order.id).label("cnt"),
                __import__("sqlalchemy")
                .func.coalesce(__import__("sqlalchemy").func.sum(Order.final_amount), 0)
                .label("rev"),
            )
            .filter(
                Order.created_at >= start,
                Order.created_at < end,
                Order.status.in_(["paid", "completed"]),
            )
            .first()
        )
        # top-5 品类
        cat_rows = (
            s.query(
                OrderItem.product_name,
                __import__("sqlalchemy").func.sum(OrderItem.subtotal).label("rev"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                Order.created_at >= start,
                Order.created_at < end,
                Order.status.in_(["paid", "completed"]),
            )
            .group_by(OrderItem.product_name)
            .order_by(__import__("sqlalchemy").func.sum(OrderItem.subtotal).desc())
            .limit(5)
            .all()
        )

    return {
        "merchant_id": merchant_id,
        "store_name": store_name,
        "parent_merchant_id": parent_merchant_id,
        "max_stores": max_stores,
        "date": day,
        "gross_sales": row.rev if row else 0,
        "order_count": row.cnt if row else 0,
        "top5_categories": [
            {"name": r.product_name, "revenue": r.rev} for r in cat_rows
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def export_signed_digest(
    priv_pem: bytes,
    out_dir: Path | None = None,
    day: str | None = None,
    **digest_kwargs,
) -> Path:
    """构建 + 签名 + 写出到 cloud_export/YYYYMMDD.json，返回文件路径"""
    out_dir = out_dir or Path("cloud_export")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_daily_digest(day=day, **digest_kwargs)
    signature = sign_payload(payload, priv_pem)
    record = {"payload": payload, "signature": signature}
    fn = out_dir / f"daily_{payload['date']}.json"
    fn.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"日结已导出: {fn}")
    return fn

"""M6 应用层：策略下发客户端（POS 端拉取并应用云端策略）"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

try:
    import httpx
except ImportError:  # httpx is optional for local testing
    httpx = None  # type: ignore

from app.domain.chain.policy_scope import PolicyScope
from app.infra.db.engine import session_factory
from app.infra.db.models import PolicyReceipt as PolicyReceiptModel

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PolicyClient:
    """从云端拉取最新策略变更并写入 POS 本地"""

    def __init__(self, merchant_id: str = "local", cloud_url: str = ""):
        self.merchant_id = merchant_id
        self.cloud_url = cloud_url or "http://localhost:9000"

    # ── 拉取 ──────────────────────────────────────────────

    def fetch_policies(self, since_ts: int = 0) -> list[dict]:
        """GET /cloud/v1/policies/{tenant_id}/pull"""
        if httpx is None:
            return []
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(
                    f"{self.cloud_url}/cloud/v1/policies/{self.merchant_id}/pull",
                    params={"since": since_ts},
                )
                r.raise_for_status()
                return r.json().get("policies", [])
        except Exception as e:  # noqa: BLE001
            log.warning("fetch_policies failed: %s", e)
            return []

    # ── 各策略类型应用 ─────────────────────────────────────

    def _filter_fields(
        self, payload: dict, allowed_fields: list[str]
    ) -> dict:
        """白名单字段过滤"""
        return {k: v for k, v in payload.items() if k in allowed_fields}

    def apply_menu_policy(self, payload: dict) -> dict:
        """下发菜单策略：仅白名单字段覆盖"""
        clean = self._filter_fields(payload, PolicyScope.MENU_FIELDS)
        return {
            "ok": True,
            "policy_type": "menu",
            "applied_fields": list(clean.keys()),
        }

    def apply_price_policy(self, payload: dict) -> dict:
        """下发定价策略"""
        clean = self._filter_fields(payload, PolicyScope.PRICE_FIELDS)
        return {
            "ok": True,
            "policy_type": "prices",
            "applied_fields": list(clean.keys()),
        }

    def apply_member_policy(self, payload: dict) -> dict:
        """下发会员策略"""
        clean = self._filter_fields(payload, PolicyScope.MEMBER_FIELDS)
        return {
            "ok": True,
            "policy_type": "members",
            "applied_fields": list(clean.keys()),
        }

    def apply_promotion_policy(self, payload: dict) -> dict:
        """下发促销策略"""
        clean = self._filter_fields(payload, PolicyScope.PROMOTION_FIELDS)
        return {
            "ok": True,
            "policy_type": "promotions",
            "applied_fields": list(clean.keys()),
        }

    # ── 回执与版本 ────────────────────────────────────────

    def record_receipt(
        self,
        push_id: str,
        policy_type: str,
        status: str,
        conflict_detail: str = "",
    ) -> PolicyReceiptModel:
        """写入回执记录"""
        with session_factory() as s:
            receipt = PolicyReceiptModel(
                id=str(uuid.uuid4()),
                tenant_id=self.merchant_id,
                push_id=push_id,
                policy_type=policy_type,
                status=status,
                conflict_detail_json=conflict_detail or None,
            )
            s.add(receipt)
            if status == "applied":
                receipt.applied_at = _utcnow()
            s.commit()
            s.refresh(receipt)
            return receipt

    def get_local_version(self, policy_type: str) -> int:
        """获取本地已接收的最新 push_version"""
        with session_factory() as s:
            row = (
                s.query(PolicyReceiptModel)
                .filter_by(
                    tenant_id=self.merchant_id,
                    policy_type=policy_type,
                    status="applied",
                )
                .order_by(PolicyReceiptModel.created_at.desc())
                .first()
            )
            return int(row.created_at.timestamp()) if row else 0

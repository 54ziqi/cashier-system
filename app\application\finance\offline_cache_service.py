"""应用层：离线缓存服务 - License 验签缓存 → 断网连续收银 N 天"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings

log = logging.getLogger(__name__)

LICENSE_CACHE_FILE = ".cashier/license_cache.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OfflineCacheService:
    """离线缓存服务：缓存 License 验签结果，支持断网时继续收银"""

    def __init__(self, settings: Settings | None = None):
        self._cache_path: Path
        if settings:
            self._cache_path = settings.home / LICENSE_CACHE_FILE
        else:
            self._cache_path = Path(LICENSE_CACHE_FILE)

    # ── 缓存读写 ────────────────────────────────────────────

    def cache_verification(self, result: Any) -> None:
        """缓存验签结果到本地 JSON 文件"""
        payload = getattr(result, "payload", None)
        status = getattr(result, "status", "unknown")
        message = getattr(result, "message", "")

        cache_data = {
            "status": status,
            "message": message,
            "payload": payload,
            "expired_at": payload.get("expire_at") if payload else None,
            "cached_at": _utcnow().isoformat(),
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"License 验签已缓存: {status}")

    def get_cached(self) -> dict | None:
        """读取缓存的 License 验签结果"""
        if not self._cache_path.exists():
            return None
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def is_valid(self) -> bool:
        """检查缓存是否有效（未过期）"""
        cached = self.get_cached()
        if not cached:
            return False
        expired_at = cached.get("expired_at")
        if not expired_at:
            return True
        try:
            expire_dt = datetime.fromisoformat(expired_at.replace("Z", "+00:00"))
            return _utcnow() < expire_dt
        except (ValueError, TypeError):
            return True

    def load_fallback(self) -> dict | None:
        """离线启动时调用：加载缓存作为 fallback"""
        cached = self.get_cached()
        if cached and cached.get("status") in ("valid", "trial", "grace"):
            log.info("离线模式：使用缓存的 License 验签结果")
            return cached
        return None

    def clear_cache(self) -> None:
        """清除缓存"""
        if self._cache_path.exists():
            try:
                self._cache_path.unlink()
                log.info("License 缓存已清除")
            except OSError as e:
                log.warning(f"清除缓存失败: {e}")

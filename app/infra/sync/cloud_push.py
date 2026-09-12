"""
云同步推送 + 队列重试

按日结文件签名 → HTTPS POST 到云端 /cloud/v1/ingest
推送失败 → 写入 .pending 队列，下次重试。
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CLOUD_URL = "http://localhost:9000"   # 覆盖为云端实际地址
PUSH_QUEUE = Path("cloud_export/.pending")


def push_digest(file: Path, cloud_url: str = CLOUD_URL, timeout: float = 10.0) -> bool:
    """推送日结文件到云端。返回 True 表示成功。"""
    record = json.loads(file.read_text(encoding="utf-8"))
    body = json.dumps({
        "payload": record["payload"],
        "sig":     record["signature"],
    }).encode()

    req = urllib.request.Request(
        f"{cloud_url}/cloud/v1/ingest",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                log.info(f"已推送到云端: {file.name}")
                return True
            else:
                log.warning(f"云端响应 {resp.status}: {file.name}")
                return False
    except Exception as e:
        log.warning(f"推送到云端失败: {e}")
        return False


def enqueue(file: Path) -> None:
    """推送失败时入队，保存 .pending 文件用于重试"""
    PUSH_QUEUE.mkdir(parents=True, exist_ok=True)
    target = PUSH_QUEUE / file.name
    target.write_text(file.read_text(encoding="utf-8"), encoding="utf-8")
    log.info(f"已入队 (待重试): {file.name}")


def retry_pending(cloud_url: str = CLOUD_URL, max_retry: int = 5) -> tuple[int, int]:
    """
    尝试重试所有 .pending 文件。返回 (成功数, 仍失败数)。
    成功即删除 .pending 文件。
    """
    if not PUSH_QUEUE.exists():
        return 0, 0
    ok, fail = 0, 0
    for f in sorted(PUSH_QUEUE.glob("daily_*.json")):
        if push_digest(f, cloud_url):
            f.unlink(missing_ok=True)
            ok += 1
        else:
            fail += 1
    return ok, fail


def scheduled_push(priv_pem: bytes, cloud_url: str = CLOUD_URL, **digest_kwargs) -> bool:
    """
    一键日结 + 签名 + 推送 + 失败入队。由 lifespan 的 scheduled job 调用。
    """
    from .daily_export import export_signed_digest
    try:
        file = export_signed_digest(priv_pem, **digest_kwargs)
        if not push_digest(file, cloud_url):
            enqueue(file)
            return False
        return True
    except Exception as e:
        log.error(f"scheduled_push 失败: {e}")
        return False

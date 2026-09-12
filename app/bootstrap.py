"""首次运行自动初始化"""
from __future__ import annotations
import secrets
import string
import logging
from pathlib import Path

from app.config import Settings
from app.infra.security.secrets import (
    load_or_create_secret,
    load_or_create_rsa_keypair,
)

log = logging.getLogger(__name__)


def _random_password(n: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def bootstrap(settings: Settings) -> None:
    settings.ensure_dirs()

    session_secret = load_or_create_secret(settings.secrets_dir / "session.key")
    load_or_create_rsa_keypair(
        settings.secrets_dir / "license_priv.pem",
        settings.secrets_dir / "license_pub.pem",
    )

    settings._session_secret = session_secret  # type: ignore[attr-defined]
    log.info("Bootstrap 完成")


def ensure_admin(settings: Settings, auth_engine) -> str | None:
    if auth_engine.user_count() > 0:
        return None
    pwd = _random_password()
    auth_engine.create_user("admin", pwd, "merchant_admin")

    pwd_file = settings.home / "data" / "initial-password.txt"
    pwd_file.write_text(
        f"用户名: admin\n密码: {pwd}\n"
        f"（首次成功登录后本文件会被自动删除）\n",
        encoding="utf-8",
    )
    try:
        pwd_file.chmod(0o600)
    except OSError:
        pass
    return pwd


def clear_initial_password_file(settings: Settings) -> None:
    """首次成功登录后自动删除密码文件"""
    pwd_file = settings.home / "data" / "initial-password.txt"
    if pwd_file.exists():
        try:
            pwd_file.unlink()
            log.info("已自动删除 initial-password.txt")
        except OSError as e:
            log.warning(f"删除密码文件失败: {e}")

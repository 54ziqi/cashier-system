"""完全离线登录：本地凭证 + bcrypt + HMAC Session + Token 撤销（session version）"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

import bcrypt
from sqlalchemy import select, text

from app.config import Settings
from app.infra.db.models import LocalCredential


class AuthError(Exception):
    pass


@dataclass
class SessionInfo:
    user_id: str
    username: str
    role: str
    expires_at: float
    jti: str = ""  # legacy 保留 (用于兼容旧字段)
    ver: int = 0  # session version at token creation


class OfflineAuthEngine:
    def __init__(self, session_factory: Callable, secret: bytes, cfg: Settings):
        self.session_factory = session_factory
        self.secret = secret
        self.cfg = cfg.security
        # 短期内存辅助 (jti 黑名单缓存, 重启清空)
        self._revoked_jtis: set[str] = set()

    def login(self, username: str, password: str) -> str:
        with self.session_factory() as s:
            cred = s.execute(
                select(LocalCredential).where(LocalCredential.username == username)
            ).scalar_one_or_none()

            if cred is None or not cred.is_active:
                raise AuthError("用户不存在或已停用")

            now = time.time()
            if cred.locked_until and cred.locked_until > now:
                left = int(cred.locked_until - now)
                raise AuthError(f"账户已锁定，请 {left}s 后重试")

            if not bcrypt.checkpw(password.encode(), cred.password_hash.encode()):
                cred.failed_attempts += 1
                if cred.failed_attempts >= self.cfg.max_login_failures:
                    cred.locked_until = now + self.cfg.lock_minutes * 60
                    cred.failed_attempts = 0
                s.commit()
                raise AuthError("密码错误")

            cred.failed_attempts = 0
            cred.locked_until = 0.0
            cred.last_login = now
            s.commit()

            return self._sign_token(
                cred.id, cred.username, cred.role, cred.token_version
            )

    def _sign_token(self, user_id: str, username: str, role: str, ver: int) -> str:
        ts = str(int(time.time()))
        jti = secrets.token_hex(16)
        payload = f"{user_id}|{username}|{role}|{ts}|{jti}|{ver}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}|{sig}"

    def verify_token(self, token: str) -> SessionInfo:
        try:
            parts = token.split("|")
            if len(parts) != 7:
                raise AuthError("Token 格式错误")
            user_id, username, role, ts, jti, ver_str, sig = parts
        except (ValueError, IndexError):
            raise AuthError("Token 格式错误")

        payload = f"{user_id}|{username}|{role}|{ts}|{jti}|{ver_str}"
        expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise AuthError("Token 无效")

        # 短期内存黑名单 (仅做辅助)
        if jti in self._revoked_jtis:
            raise AuthError("Token 已被撤销")

        # 持久校验: token_version 必须与 DB 当前值一致
        try:
            ver = int(ver_str)
        except ValueError:
            raise AuthError("Token 格式错误: 非法 ver")

        with self.session_factory() as s:
            cred = s.execute(
                select(LocalCredential.token_version).where(
                    LocalCredential.id == user_id
                )
            ).scalar_one_or_none()
            if cred is None:
                raise AuthError("Token 无效: 用户不存在")
            if ver != cred:  # DB 中 token_version 已变 → 该 token 失效
                raise AuthError("Token 已被撤销")

        expires = float(ts) + self.cfg.session_hours * 3600
        if time.time() > expires:
            raise AuthError("Token 已过期")
        return SessionInfo(user_id, username, role, expires, jti, ver)

    def revoke_token(self, token: str) -> None:
        """撤销 token：递增对应 LocalCredential.token_version 使 token 失效"""
        # 先写到内存黑名单 (短期防重放)
        try:
            parts = token.split("|")
            if len(parts) == 7:
                jti = parts[4]
                self._revoked_jtis.add(jti)
        except Exception:
            pass

        # 持久化: 递增 DB 中该用户的所有 token_version
        user_id = None
        try:
            info = self.verify_token(token)
            user_id = info.user_id
        except AuthError:
            # token 已过期/无效但可能 jti 已解析，尝试提取 user_id
            try:
                parts = token.split("|")
                if len(parts) == 7:
                    user_id = parts[0]
            except Exception:
                pass
        if not user_id:
            return

        with self.session_factory() as s:
            s.execute(
                text(
                    "UPDATE local_credentials SET token_version = token_version + 1 WHERE id = :uid"
                ),
                {"uid": user_id},
            )
            s.commit()

    def revoke_all_for_user(self, user_id: str) -> int:
        """撤回某用户的所有 token（递增其 token_version）"""
        with self.session_factory() as s:
            s.execute(
                text(
                    "UPDATE local_credentials SET token_version = token_version + 1 WHERE id = :uid"
                ),
                {"uid": user_id},
            )
            s.commit()
        return 1

    def create_user(self, username: str, password: str, role: str) -> str:
        import uuid

        uid = str(uuid.uuid4())
        pw_hash = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt(rounds=self.cfg.bcrypt_rounds),
        ).decode()
        with self.session_factory() as s:
            s.add(
                LocalCredential(
                    id=uid,
                    username=username,
                    password_hash=pw_hash,
                    role=role,
                )
            )
            s.commit()
        return uid

    def user_count(self) -> int:
        from sqlalchemy import func

        with self.session_factory() as s:
            return s.execute(
                select(func.count()).select_from(LocalCredential)
            ).scalar_one()

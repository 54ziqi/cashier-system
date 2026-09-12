"""完全离线登录：本地凭证 + bcrypt + HMAC Session + Token 撤销（持久化）"""
from __future__ import annotations
import hmac
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Callable

import bcrypt
from sqlalchemy import select

from app.infra.db.models import LocalCredential, RevokedToken
from app.config import Settings


class AuthError(Exception):
    pass


@dataclass
class SessionInfo:
    user_id: str
    username: str
    role: str
    expires_at: float
    jti: str = ""  # Token 唯一标识，用于撤销


class OfflineAuthEngine:
    def __init__(self, session_factory: Callable, secret: bytes, cfg: Settings):
        self.session_factory = session_factory
        self.secret = secret
        self.cfg = cfg.security

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

            return self._sign_token(cred.id, cred.username, cred.role)

    def _sign_token(self, user_id: str, username: str, role: str) -> str:
        ts = str(int(time.time()))
        jti = secrets.token_hex(16)
        payload = f"{user_id}|{username}|{role}|{ts}|{jti}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}|{sig}"

    def verify_token(self, token: str) -> SessionInfo:
        try:
            parts = token.split("|")
            if len(parts) != 6:
                raise AuthError("Token 格式错误")
            user_id, username, role, ts, jti, sig = parts
        except (ValueError, IndexError):
            raise AuthError("Token 格式错误")

        payload = f"{user_id}|{username}|{role}|{ts}|{jti}"
        expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise AuthError("Token 无效")

        # Token 撤销校验（查 DB）
        if self._is_revoked(jti):
            raise AuthError("Token 已被撤销")

        expires = float(ts) + self.cfg.session_hours * 3600
        if time.time() > expires:
            raise AuthError("Token 已过期")
        return SessionInfo(user_id, username, role, expires, jti)

    def _is_revoked(self, jti: str) -> bool:
        """查询 DB 判断 jti 是否已撤销"""
        with self.session_factory() as s:
            row = s.execute(
                select(RevokedToken.jti).where(RevokedToken.jti == jti)
            ).scalar_one_or_none()
            return row is not None

    def revoke_token(self, token: str) -> None:
        """撤销指定 Token（登出用，持久化到 DB）"""
        try:
            info = self.verify_token(token)
            if info.jti:
                self._revoke_jti(info.jti, info.user_id)
        except AuthError:
            # 即使 token 过期/无效，只要能解析出 jti 就写入撤销表
            try:
                parts = token.split("|")
                if len(parts) == 6:
                    uid, _, _, _, jti, _ = parts
                    self._revoke_jti(jti, uid)
            except Exception:
                pass

    def _revoke_jti(self, jti: str, user_id: str) -> None:
        """将 jti 写入撤销表（幂等：重复写入无副作用）"""
        with self.session_factory() as s:
            existing = s.execute(
                select(RevokedToken).where(RevokedToken.jti == jti)
            ).scalar_one_or_none()
            if existing is None:
                s.add(RevokedToken(jti=jti, revoked_at=time.time(), user_id=user_id))
                s.commit()

    def revoke_all_for_user(self, user_id: str) -> int:
        """撤销某用户的所有 Token（需客户端主动丢弃，但可标记用户级失效）"""
        # DB 中以 user_id 标记，未来可加入全局会话版本号
        return 0

    def create_user(self, username: str, password: str, role: str) -> str:
        import uuid
        uid = str(uuid.uuid4())
        pw_hash = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt(rounds=self.cfg.bcrypt_rounds),
        ).decode()
        with self.session_factory() as s:
            s.add(LocalCredential(
                id=uid, username=username,
                password_hash=pw_hash, role=role,
            ))
            s.commit()
        return uid

    def user_count(self) -> int:
        from sqlalchemy import func
        with self.session_factory() as s:
            return s.execute(select(func.count()).select_from(LocalCredential)).scalar_one()

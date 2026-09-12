"""完全离线登录：本地凭证 + bcrypt + HMAC Session"""
from __future__ import annotations
import hmac
import hashlib
import time
from dataclasses import dataclass

import bcrypt
from sqlalchemy import String, Integer, Float, select
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.engine import Base
from app.config import Settings


class LocalCredential(Base):
    __tablename__ = "local_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[float] = mapped_column(Float, default=0.0)
    last_login: Mapped[float] = mapped_column(Float, default=0.0)


class AuthError(Exception):
    pass


@dataclass
class SessionInfo:
    user_id: str
    username: str
    role: str
    expires_at: float


class OfflineAuthEngine:
    def __init__(self, session_factory, secret: bytes, cfg: Settings):
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
        payload = f"{user_id}|{username}|{role}|{ts}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}|{sig}"

    def verify_token(self, token: str) -> SessionInfo:
        try:
            user_id, username, role, ts, sig = token.split("|")
        except ValueError:
            raise AuthError("Token 格式错误")
        payload = f"{user_id}|{username}|{role}|{ts}"
        expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise AuthError("Token 无效")
        expires = float(ts) + self.cfg.session_hours * 3600
        if time.time() > expires:
            raise AuthError("Token 已过期")
        return SessionInfo(user_id, username, role, expires)

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

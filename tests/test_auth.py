"""Auth 模块测试：登录 / Token 验证 / 过期 / 撤销 / 暴力锁定"""
from __future__ import annotations
import time

import pytest

from app.kernel.auth.engine import OfflineAuthEngine, AuthError, SessionInfo
from tests.conftest import _TEST_ADMIN_PWD


class TestOfflineAuthEngine:
    """OfflineAuthEngine 单元测试"""

    def test_login_success(self, auth_engine):
        """正确密码应返回 Token"""
        token = auth_engine.login("admin", self._get_admin_password(auth_engine))
        assert isinstance(token, str)
        assert len(token) > 50
        assert token.count("|") == 5  # 包含 jti

    def test_login_wrong_password(self, auth_engine):
        """错误密码应抛出 AuthError"""
        with pytest.raises(AuthError, match="密码错误"):
            auth_engine.login("admin", "wrong-password")

    def test_login_nonexistent_user(self, auth_engine):
        """不存在的用户应抛出 AuthError"""
        with pytest.raises(AuthError, match="用户不存在或已停用"):
            auth_engine.login("nobody", "whatever")

    def test_verify_valid_token(self, auth_engine):
        """有效 Token 应返回 SessionInfo"""
        token = auth_engine.login("admin", self._get_admin_password(auth_engine))
        info = auth_engine.verify_token(token)
        assert isinstance(info, SessionInfo)
        assert info.username == "admin"
        assert info.role == "merchant_admin"
        assert info.jti  # 非空 jti
        assert info.expires_at > time.time()

    def test_verify_invalid_format(self, auth_engine):
        """格式错误的 Token 应抛出 AuthError"""
        with pytest.raises(AuthError, match="Token 格式错误"):
            auth_engine.verify_token("garbage")

    def test_verify_tampered_token(self, auth_engine):
        """篡改过的 Token 应抛出 AuthError"""
        token = auth_engine.login("admin", self._get_admin_password(auth_engine))
        # 篡改最后几个字符
        tampered = token[:-10] + "deadbeef00"
        with pytest.raises(AuthError, match="Token 无效"):
            auth_engine.verify_token(tampered)

    def test_verify_expired_token(self, auth_engine, monkeypatch):
        """过期 Token 应被拒绝"""
        import app.kernel.auth.engine as engine_mod
        # monkeypatch: 将 session_hours 设为极小值
        token = auth_engine.login("admin", self._get_admin_password(auth_engine))
        monkeypatch.setattr(auth_engine.cfg, "session_hours", -1)  # 立即过期
        with pytest.raises(AuthError, match="Token 已过期"):
            auth_engine.verify_token(token)

    @pytest.fixture(autouse=True)
    def _reset_lock(self, auth_engine):
        """每个测试清除锁定状态"""
        yield
        # 解锁
        from app.infra.db.engine import session_factory
        from app.infra.db.models import LocalCredential
        try:
            with session_factory() as s:
                cred = s.query(LocalCredential).filter_by(username="admin").first()
                if cred and cred.locked_until:
                    cred.locked_until = 0.0
                    cred.failed_attempts = 0
                    s.commit()
        except Exception:
            pass

    def test_lockout_after_max_failures(self, auth_engine):
        """连续失败 max_login_failures 次应锁定账户"""
        max_fail = auth_engine.cfg.max_login_failures
        for _ in range(max_fail):
            try:
                auth_engine.login("admin", "wrong-password")
            except AuthError as e:
                assert "密码错误" in str(e) or "锁定" in str(e)
        # 下一次即使正确密码也应被锁定
        with pytest.raises(AuthError, match="锁定"):
            auth_engine.login("admin", self._get_admin_password(auth_engine))

    def test_token_revocation(self, auth_engine):
        """撤销后的 Token 应无法使用"""
        token = auth_engine.login("admin", self._get_admin_password(auth_engine))
        # 先验证正常
        info = auth_engine.verify_token(token)
        assert info.jti
        # 撤销 Token
        auth_engine.revoke_token(token)
        # 再次验证应失败
        with pytest.raises(AuthError, match="撤销"):
            auth_engine.verify_token(token)

    def test_revoke_invalid_token_silent(self, auth_engine):
        """撤销无效 Token 不应报错"""
        auth_engine.revoke_token("invalid-token-no-exist")  # 不应抛异常

    def test_new_token_after_revoke(self, auth_engine):
        """撤销旧 Token 后，新 Token 仍可用"""
        token1 = auth_engine.login("admin", self._get_admin_password(auth_engine))
        auth_engine.revoke_token(token1)
        token2 = auth_engine.login("admin", self._get_admin_password(auth_engine))
        info = auth_engine.verify_token(token2)
        assert info.jti != token1.split("|")[4]  # 不同 jti

    def _get_admin_password(self, auth_engine) -> str:
        """返回测试用 admin 密码"""
        return _TEST_ADMIN_PWD


class TestAuthAPI:
    """Auth HTTP API 集成测试"""

    def test_login_endpoint(self, client):
        """POST /api/v1/auth/login 应返回 token"""
        pwd = self._get_admin_pwd(client)
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": pwd})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token_type"] == "local"
        assert data["token"].count("|") == 5  # 含 jti

    def test_login_wrong_password_401(self, client):
        """错误密码返回 401"""
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_logout_requires_token(self, client):
        """登出无 Token 应返回 401"""
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    def test_logout_revokes_token(self, client):
        """登出后 Token 失效"""
        pwd = self._get_admin_pwd(client)
        login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": pwd})
        token = login_resp.json()["token"]

        # 登出
        logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout_resp.status_code == 200

        # Token 已失效
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 401

    def test_me_endpoint(self, client):
        """/me 返回当前用户信息"""
        pwd = self._get_admin_pwd(client)
        login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": pwd})
        token = login_resp.json()["token"]
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "merchant_admin"

    def _get_admin_pwd(self, client) -> str:
        return _TEST_ADMIN_PWD

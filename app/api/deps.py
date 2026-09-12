"""API 依赖注入"""
from __future__ import annotations
from fastapi import Request, HTTPException, Depends

from app.infra.db.engine import session_factory


async def get_current_user(request: Request):
    """从 Bearer Token 验证当前用户"""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 Token 格式错误")
    try:
        return request.app.state.auth.verify_token(auth[7:])
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


async def require_admin(user=Depends(get_current_user)):
    """要求当前用户为管理员角色"""
    if user.role != "merchant_admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return user


def get_db():
    """获取数据库会话"""
    with session_factory() as s:
        yield s

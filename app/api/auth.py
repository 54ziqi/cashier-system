from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.kernel.auth.engine import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginReq, request: Request):
    engine = request.app.state.auth
    try:
        token = engine.login(req.username, req.password)
    except AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": token, "token_type": "local"}


@router.get("/me")
async def me(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "缺少 Token")
    try:
        info = request.app.state.auth.verify_token(auth[7:])
    except AuthError as e:
        raise HTTPException(401, str(e))
    return {"user_id": info.user_id, "username": info.username, "role": info.role}

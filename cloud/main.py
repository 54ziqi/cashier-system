"""
柒号收银系统 · 云端聚合服务

独立入口：python -m cloud.main
启动后端 (聚合 API + WebSocket + 看板页面)。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from .auth import ensure_pubkey_on_startup, verify_digest
from .models import TenantRegistry, init_db
from .service import aggregate_chain, aggregate_single, ingest_digest, list_chain_stores

log = logging.getLogger("cloud")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

bearer = HTTPBearer(auto_error=False)

# ── 全局状态（main() 中初始化） ──────────────────────────────────────

SessionLocal = None  # type: ignore

# ── CORS 白名单 ──────────────────────────────────────────────────────

_ALLOWED_ORIGIN: str = os.environ.get("CLOUD_DASHBOARD_ORIGIN", "http://localhost:9000")


class ConnectionManager:
    """按 parent_merchant_id 管理 WebSocket 连接"""

    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = {}

    def connect(self, ws: WebSocket, parent_id: str):
        """注册到房间 (调用方负责 ws.accept())"""
        self._rooms.setdefault(parent_id, []).append(ws)

    def disconnect(self, ws: WebSocket, parent_id: str):
        group = self._rooms.get(parent_id, [])
        if ws in group:
            group.remove(ws)
        if not group:
            self._rooms.pop(parent_id, None)

    async def broadcast(self, parent_id: str, data: dict):
        dead = []
        for ws in self._rooms.get(parent_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, parent_id)


manager = ConnectionManager()

app = FastAPI(title="柒号收银 · 云端聚合", version="3.2.0")


@app.on_event("startup")
async def _startup_validate():
    ensure_pubkey_on_startup(
        Path(os.environ.get("CLOUD_PUBKEY_PATH", "cloud/data/license_pub.pem"))
    )


@app.middleware("http")
async def _cors_whitelist(request: Request, call_next):
    """同源放行；非白名单 Origin 不放行"""
    origin = request.headers.get("origin")
    response = await call_next(request)
    if origin is None:
        return response
    host = request.headers.get("host", "")
    self_origins = {f"http://{host}", f"https://{host}"}
    if origin in self_origins:
        return response
    if origin != _ALLOWED_ORIGIN:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Origin '{origin}' not allowed by CORS whitelist"},
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[_ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 鉴权 ─────────────────────────────────────────────────────────────


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(credentials) -> Optional[str]:
    """从 Bearer credentials 中提取 token 字符串"""
    if not credentials or not credentials.credentials:
        raise HTTPException(401, "未授权：缺少 Bearer Token")
    return credentials.credentials


def _lookup_active_tenant(db: Session, token: str):
    """在 TenantRegistry 中查找 active tenant, 找不到返回 None"""
    return db.query(TenantRegistry).filter_by(merchant_id=token, active=True).first()


class _MerchantAuthDep:
    """
    Callable class: 把 parent_id/merchant_id 缓存在实例中, 供 FastAPI Depends 调用。
    避免模块加载期依赖尚未存在的函数参数。
    """

    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    def __call__(
        self,
        request: Request,
        credentials=Depends(bearer),
        db: Session = Depends(get_db),
    ):
        # request.path_params.get 在运行时拿到真正的 merchant_id
        mid = self.merchant_id or request.path_params.get("merchant_id", "")
        return _require_admin_for_merchant(mid, credentials, db)


def require_admin(credentials=Depends(bearer), db: Session = Depends(get_db)):
    """
    严格校验 token:
    1. 从 Bearer 取 token
    2. 作为 merchant_id 在 TenantRegistry 中 lookup
    3. 找不到则 401
    4. 降级兼容: reg 表仍空时暂时放行 (首次 ingest 注册后再开启校验)
    """
    token = _extract_token(credentials)
    if db.query(TenantRegistry).count() == 0:
        return token
    tenant = _lookup_active_tenant(db, token)
    if not tenant:
        raise HTTPException(401, "未授权：无效 Token（未找到对应商户）")
    return token


def _require_admin_for_merchant(
    merchant_id: str, credentials=Depends(bearer), db: Session = Depends(get_db)
):
    """
    GET /dashboard/{merchant_id} 的权限校验:
    - token == merchant_id (本 merchant 读自己的 dash)
    - token 是 parent of merchant_id (母店可读子店 dash)
    """
    token = _extract_token(credentials)
    if db.query(TenantRegistry).count() == 0:
        return token
    tenant = _lookup_active_tenant(db, token)
    if not tenant:
        raise HTTPException(401, "未授权：无效 Token")
    # 自己读自己
    if token == merchant_id:
        return token
    # 母店读子店: 检查 merchant_id 的 parent_merchant_id == token
    target = _lookup_active_tenant(db, merchant_id)
    if target and target.parent_merchant_id == token:
        return token
    raise HTTPException(403, "越权：无权访问该商户 dashboard")


def _check_chain_access(parent_id: str, credentials, db: Session) -> str:
    """校验 chain 访问权限: 母店 token 可读自己的 chain, 子店 token 可读父 chain"""
    if not credentials or not credentials.credentials:
        raise HTTPException(401, "未授权：缺少 Bearer Token")
    token = credentials.credentials
    if db.query(TenantRegistry).count() == 0:
        return token
    tenant = db.query(TenantRegistry).filter_by(merchant_id=token, active=True).first()
    if not tenant:
        raise HTTPException(401, "未授权")
    if tenant.merchant_id != parent_id and tenant.parent_merchant_id != parent_id:
        raise HTTPException(403, "越权：无权访问该 chain")
    return token


# ── API ──────────────────────────────────────────────────────────────


@app.post("/cloud/v1/ingest")
async def ingest(body: dict, db: Session = Depends(get_db)):
    """
    接收 POS 推送的日结签名数据。
    验签通过 → 入库 → WebSocket 广播给母店所有看板。
    """
    payload = body.get("payload", {})
    sig = body.get("sig", "")
    if not payload:
        raise HTTPException(400, "缺少 payload")
    if not verify_digest(payload, sig):
        raise HTTPException(400, "签名校验失败")

    d = ingest_digest(db, payload, sig)

    parent_id = payload.get("parent_merchant_id") or payload["merchant_id"]
    await manager.broadcast(
        parent_id,
        {
            "type": "digest.new",
            "data": {
                "merchant_id": payload["merchant_id"],
                "date": payload["date"],
                "gross_sales": payload.get("gross_sales", 0),
                "order_count": payload.get("order_count", 0),
                "store_name": payload.get("store_name", ""),
            },
        },
    )

    return {"ok": True, "id": d.id}


@app.get("/cloud/v1/dashboard/{merchant_id}")
async def single_dashboard(
    merchant_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    tok=Depends(_MerchantAuthDep(merchant_id="")),
):
    return aggregate_single(db, merchant_id, days)


@app.get("/cloud/v1/chain/{parent_id}/summary")
async def chain_summary(
    parent_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    credentials=Depends(bearer),
):
    _check_chain_access(parent_id, credentials, db)
    return aggregate_chain(db, parent_id, days)


@app.get("/cloud/v1/chain/{parent_id}/stores")
async def chain_stores(
    parent_id: str, db: Session = Depends(get_db), credentials=Depends(bearer)
):
    _check_chain_access(parent_id, credentials, db)
    stores = list_chain_stores(db, parent_id)
    return {
        "parent_id": parent_id,
        "stores": stores,
        "local_only": False,
    }


@app.get("/cloud/v1/tenants")
async def list_tenants(db: Session = Depends(get_db), tok=Depends(require_admin)):
    rows = db.query(TenantRegistry).filter_by(active=True).all()
    return [
        {
            "merchant_id": r.merchant_id,
            "store_name": r.store_name,
            "parent_id": r.parent_merchant_id,
            "tier": r.tier,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        }
        for r in rows
    ]


# ── WebSocket 鉴权 ──────────────────────────────────────────────────


@app.websocket("/cloud/ws/{parent_id}")
async def ws_endpoint(ws: WebSocket, parent_id: str):
    """
    云看板母店实时通道。
    P0-C3: 接受连接后校验 auth_frame, 失败则 close(4001)
    """
    await ws.accept()
    try:
        auth_frame = await ws.receive_text()
    except Exception:
        await ws.close(code=4001)
        return
    try:
        msg = json.loads(auth_frame)
    except (json.JSONDecodeError, ValueError, TypeError):
        await ws.close(code=4001)
        return
    token = msg.get("token", "")
    if not token:
        await ws.close(code=4001)
        return
    db = SessionLocal()
    try:
        tenant = (
            db.query(TenantRegistry).filter_by(merchant_id=token, active=True).first()
        )
        if not tenant:
            await ws.close(code=4001)
            return
    finally:
        db.close()

    manager.connect(ws, parent_id)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws, parent_id)


# ── 云看板页面 ───────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def cloud_dashboard():
    """柒号收银 · 云端数据看板入口"""
    html = (Path(__file__).parent / "static" / "cloud_dashboard.html").read_text()
    return HTMLResponse(content=html)


# ── CLI 入口 ─────────────────────────────────────────────────────────


def main():
    ensure_pubkey_on_startup(
        Path(os.environ.get("CLOUD_PUBKEY_PATH", "cloud/data/license_pub.pem"))
    )

    p = argparse.ArgumentParser(description="柒号收银 · 云端聚合服务")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--db", default="cloud/data/cloud.db")
    args = p.parse_args()

    global SessionLocal
    SessionLocal = init_db(args.db)

    uvicorn.run("cloud.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

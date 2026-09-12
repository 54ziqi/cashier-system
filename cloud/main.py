"""
柒号收银系统 · 云端聚合服务

独立入口：python -m cloud.main
启动后端 (聚合 API + WebSocket + 看板页面)。
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from .auth import verify_digest
from .models import Base, DailyDigest, TenantRegistry, init_db
from .service import aggregate_chain, aggregate_single, ingest_digest, list_chain_stores

log = logging.getLogger("cloud")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SessionLocal = init_db()

app = FastAPI(title="柒号收银 · 云端聚合", version="3.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer(auto_error=False)

# ── WebSocket 连接管理 ───────────────────────────────────────────────

class ConnectionManager:
    """按 parent_merchant_id 管理 WebSocket 连接"""

    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, parent_id: str):
        await ws.accept()
        self._rooms.setdefault(parent_id, []).append(ws)

    def disconnect(self, ws: WebSocket, parent_id: str):
        group = self._rooms.get(parent_id, [])
        if ws in group:
            group.remove(ws)
        if not group:
            self._rooms.pop(parent_id, None)

    async def broadcast(self, parent_id: str, data: dict):
        """向母店所有连接推送实时更新"""
        dead = []
        for ws in self._rooms.get(parent_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, parent_id)


manager = ConnectionManager()


# ── 鉴权 ─────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(credentials=Depends(bearer), db: Session = Depends(get_db)):
    """云端独立账号校验：header Bearer <cloud_admin_token>"""
    if not credentials or not credentials.credentials:
        raise HTTPException(401, "未授权")
    # 简版：首个注册的 tenant 为管理员
    first = db.query(TenantRegistry).filter_by(active=True).order_by(TenantRegistry.first_seen).first()
    if not first:
        raise HTTPException(403, "未激活")
    return credentials.credentials


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

    # WebSocket 广播：如果是子店数据，向母店 parent 推送
    parent_id = payload.get("parent_merchant_id") or payload["merchant_id"]
    await manager.broadcast(parent_id, {
        "type": "digest.new",
        "data": {
            "merchant_id": payload["merchant_id"],
            "date": payload["date"],
            "gross_sales": payload.get("gross_sales", 0),
            "order_count": payload.get("order_count", 0),
            "store_name": payload.get("store_name", ""),
        },
    })

    return {"ok": True, "id": d.id}


@app.get("/cloud/v1/dashboard/{merchant_id}")
async def single_dashboard(merchant_id: str, days: int = 7, db: Session = Depends(get_db),
                           tok=Depends(require_admin)):
    return aggregate_single(db, merchant_id, days)


@app.get("/cloud/v1/chain/{parent_id}/summary")
async def chain_summary(parent_id: str, days: int = 7, db: Session = Depends(get_db),
                        tok=Depends(require_admin)):
    return aggregate_chain(db, parent_id, days)


@app.get("/cloud/v1/chain/{parent_id}/stores")
async def chain_stores(parent_id: str, db: Session = Depends(get_db),
                       tok=Depends(require_admin)):
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


# ── WebSocket 实时推送 ───────────────────────────────────────────────

@app.websocket("/cloud/ws/{parent_id}")
async def ws_endpoint(ws: WebSocket, parent_id: str):
    """
    云看板母店实时通道。
    POS 端新日结入库时触发 broadcast → 看板即时刷新。
    """
    await manager.connect(ws, parent_id)
    try:
        while True:
            # 接收心跳
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
    p = argparse.ArgumentParser(description="柒号收银 · 云端聚合服务")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--db", default="cloud/data/cloud.db")
    args = p.parse_args()

    # 让 init_db 用正确的 db 路径
    global SessionLocal
    SessionLocal = init_db(args.db)

    uvicorn.run("cloud.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

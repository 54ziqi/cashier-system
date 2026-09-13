#!/usr/bin/env python3
"""柒号收银系统 - Android/Desktop 双平台入口

Desktop 模式:
    python run.py serve --profile lite

Android (Chaquopy) 模式:
    Bridge.startServer() 调用 serve(port)
    Bridge.scanUsbDevices() 等通过 Android USB/BLE API 读取
    Bridge.stopServer() 调用 shutdown()
"""

from __future__ import annotations

import socket
from threading import Event, Thread

# 全局停止事件
_shutdown_event = Event()
_android_ctx = {}


def set_android_context(ctx: dict) -> None:
    """注入 Android 运行时配置（由 Bridge 调用）"""
    global _android_ctx
    _android_ctx = ctx
    import os
    data_dir = ctx.get("data_dir")
    if data_dir:
        os.environ["CASHIER_HOME"] = data_dir
        os.makedirs(data_dir, exist_ok=True)


def get_android_context() -> dict:
    return dict(_android_ctx)


def shutdown() -> None:
    """通知服务停止"""
    _shutdown_event.set()


def find_free_port(host: str = "127.0.0.1", start: int = 8000) -> int:
    """查找可用端口"""
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return -1


def serve(port: int = 8000) -> None:
    """启动 uvicorn 服务（供 Android Chaquopy 调用）"""
    from app import create_app, setup_logging
    from app.bootstrap import bootstrap
    from app.config import load_settings

    settings = load_settings("lite")
    setup_logging(settings)
    bootstrap(settings)

    settings.server.port = port
    settings.server.open_browser = False

    app = create_app(settings)

    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=1,
        reload=False,
        access_log=False,
        log_level="warning",
    )


# ================================================================
# Desktop CLI
# ================================================================

from app.cli import main  # noqa: E402

if __name__ == "__main__":
    main()

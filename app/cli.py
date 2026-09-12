"""cashier 命令组"""
from __future__ import annotations
import argparse
import socket
import sys
import webbrowser
from pathlib import Path

from app.config import load_settings
from app.bootstrap import bootstrap
from app import create_app, setup_logging


def _find_port(host: str, start: int, auto: bool) -> int:
    if not auto:
        return start
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host if host != "0.0.0.0" else "", p))
                return p
            except OSError:
                continue
    raise RuntimeError("找不到可用端口")


def cmd_serve(args):
    settings = load_settings(args.profile)
    setup_logging(settings)
    bootstrap(settings)

    port = _find_port(settings.server.host, args.port or settings.server.port,
                      settings.server.auto_port)
    settings.server.port = port

    app = create_app(settings)

    if settings.server.open_browser and not args.no_browser:
        import threading
        url = f"http://localhost:{port}"
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run(
        app,
        host=settings.server.host,
        port=port,
        workers=1,
        reload=False,
        access_log=False,
        log_level="warning",
    )


def cmd_init(args):
    settings = load_settings(args.profile)
    setup_logging(settings)
    bootstrap(settings)

    from app.infra.db.engine import init_engine
    from app.infra.db.migrations import run_migrations
    init_engine(settings)
    tables = run_migrations()
    print(f"✅ 初始化完成")
    print(f"   数据目录: {settings.home}")
    print(f"   数据库:   {settings.db_path}")
    print(f"   已建表:   {len(tables)} 张")


def cmd_license(args):
    settings = load_settings(args.profile)

    if args.action == "status":
        from app.kernel.license.verifier import LicenseVerifier
        pub = (settings.secrets_dir / "license_pub.pem")
        if not pub.exists():
            print("❌ 未初始化，请先运行 cashier init")
            sys.exit(1)
        verifier = LicenseVerifier(pub.read_bytes(),
                                   grace_days=settings.license.grace_days)
        r = verifier.verify(settings.license_path)
        print(f"状态: {r.status}")
        print(f"说明: {r.message}")
        if r.payload:
            print(f"类型: {r.payload.get('type')}")
            print(f"到期: {r.payload.get('expire_at')}")
    elif args.action == "import":
        src = Path(args.file).expanduser()
        if not src.exists():
            print(f"❌ 文件不存在: {src}")
            sys.exit(1)
        settings.license_path.parent.mkdir(parents=True, exist_ok=True)
        settings.license_path.write_bytes(src.read_bytes())
        print(f"✅ License 已导入: {settings.license_path}")


def cmd_backup(args):
    import zipfile
    from datetime import datetime

    settings = load_settings(args.profile)
    if not settings.db_path.exists():
        print("❌ 数据库不存在")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.to).expanduser() if args.to else settings.backup_dir / f"backup-{ts}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(settings.db_path, arcname="cashier.db")
        if settings.license_path.exists():
            z.write(settings.license_path, arcname="license.lic")

    print(f"✅ 备份完成: {out}")


def cmd_status(args):
    settings = load_settings(args.profile)
    print(f"配置目录: {settings.home}")
    print(f"数据目录: {settings.home / 'data'}")
    print(f"数据库:   {settings.db_path}  ({'存在' if settings.db_path.exists() else '不存在'})")
    print(f"License:  {settings.license_path}  ({'存在' if settings.license_path.exists() else '不存在'})")


def main():
    parser = argparse.ArgumentParser(prog="cashier", description="轻量级离线收银系统")
    parser.add_argument("--profile", default="lite", help="运行档位: lite/standard")
    sub = parser.add_subparsers(dest="cmd")

    p_serve = sub.add_parser("serve", help="启动服务")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--no-browser", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_init = sub.add_parser("init", help="初始化")
    p_init.set_defaults(func=cmd_init)

    p_lic = sub.add_parser("license", help="授权管理")
    p_lic.add_argument("action", choices=["status", "import"])
    p_lic.add_argument("--file", default=None)
    p_lic.set_defaults(func=cmd_license)

    p_bak = sub.add_parser("backup", help="备份数据")
    p_bak.add_argument("--to", default=None)
    p_bak.set_defaults(func=cmd_backup)

    p_st = sub.add_parser("status", help="查看状态")
    p_st.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()

# -*- mode: python ; coding: utf-8 -*-
"""
柒号收银系统 v3.2 - PyInstaller 打包配置文件 (Windows)
入口: ../../run.py（相对于本文件位置，指向项目根目录的 run.py）
输出: 单目录模式，不显示控制台窗口，GUI 应用
"""

import os
import sys
from pathlib import Path

# ── 基础路径 ──────────────────────────────────────────────────────
# 本 spec 文件位于: 打包/win/构建脚本/cashier.spec
# 项目根目录（上溯两级）
SPEC_DIR = Path(SPECPATH)                          # 打包/win/构建脚本/
PROJECT_ROOT = SPEC_DIR.parent.parent.parent       # 项目根目录 /mnt/.../收银系统/
BUILD_ROOT = PROJECT_ROOT / "打包"                  # 打包/

# ── 数据文件 ──────────────────────────────────────────────────────
# 静态资源: html / css / js → 打包到静态资源/ 下
# 配置模板: default.toml / lite.toml → 打包到配置/ 下

DATA_SOURCES = [
    # (源绝对路径, 打包内目标相对路径)
    (str(BUILD_ROOT / "软件源/静态资源/html"), "static/html"),
    (str(BUILD_ROOT / "软件源/静态资源/css"),  "static/css"),
    (str(BUILD_ROOT / "软件源/静态资源/js"),   "static/js"),
    (str(BUILD_ROOT / "配置模板/default.toml"), "config/default.toml"),
    (str(BUILD_ROOT / "配置模板/lite.toml"),    "config/lite.toml"),
]

# 过滤掉不存在的路径，避免 PyInstaller 报错
DATAS = [(src, dst) for src, dst in DATA_SOURCES if os.path.exists(src)]

# ── 隐藏导入 ──────────────────────────────────────────────────────
# 确保 PyInstaller 不会遗漏运行时动态导入的模块
HIDDEN_IMPORTS = [
    # ── FastAPI / Uvicorn 生态 ──
    "fastapi",
    "fastapi.routing",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.staticfiles",
    "uvicorn",
    "uvicorn.config",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.server",
    "h11",
    "starlette",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.staticfiles",
    "starlette.applications",
    "starlette.responses",
    "starlette.requests",
    "starlette.exceptions",
    # ── SQLAlchemy ──
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.sql",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    # ── Pydantic ──
    "pydantic",
    "pydantic.fields",
    "pydantic_settings",
    # ── 加密与安全 ──
    "bcrypt",
    "cryptography",
    "cryptography.fernet",
    # ── app 核心模块 ──
    "app",
    "app.bootstrap",
    "app.cli",
    "app.config",
    "app.lifespan",
    "app.agents",
    "app.agents.base",
    "app.agents.anomaly",
    "app.agents.recommendation",
    "app.agents.stock_alert",
    "app.api",
    "app.api.auth",
    "app.api.dashboard",
    "app.api.deps",
    "app.api.health",
    "app.api.admin.licenses",
    "app.api.admin.tenants",
    "app.api.merchant.cashier",
    "app.api.merchant.categories",
    "app.api.merchant.finance",
    "app.api.merchant.inventory",
    "app.api.merchant.kds",
    "app.api.merchant.membership",
    "app.api.merchant.orders",
    "app.api.merchant.policy",
    "app.api.merchant.print",
    "app.api.merchant.products",
    "app.api.merchant.promotions",
    "app.api.merchant.tables",
    "app.application",
    "app.application.campaign.campaign_service",
    "app.application.chain",
    "app.application.chain.policy_client",
    "app.application.chain.settlement_service",
    "app.application.chain.transfer_service",
    "app.application.checkout",
    "app.application.checkout.checkout_service",
    "app.application.finance",
    "app.application.finance.offline_cache_service",
    "app.application.finance.report_service",
    "app.application.inventory",
    "app.application.inventory.inventory_service",
    "app.application.inventory.physical_count_service",
    "app.application.inventory.production_service",
    "app.application.kds",
    "app.application.kds.kds_service",
    "app.application.member",
    "app.application.member.level_service",
    "app.application.member.member_service",
    "app.application.member.points_service",
    "app.application.member.tag_service",
    "app.application.member.wallet_service",
    "app.application.payment",
    "app.application.payment.payment_service",
    "app.application.print",
    "app.application.print.escpos_service",
    "app.application.product",
    "app.application.product.category_service",
    "app.application.product.product_service",
    "app.application.product.spec_validator",
    "app.application.promotion.coupon_service",
    "app.application.promotion.rule_engine",
    "app.application.table",
    "app.application.table.table_service",
    "app.domain",
    "app.domain.catalog",
    "app.domain.catalog.product",
    "app.domain.chain",
    "app.domain.chain.policy_scope",
    "app.domain.identity",
    "app.domain.industry",
    "app.domain.industry.industry",
    "app.domain.membership",
    "app.domain.membership.member",
    "app.domain.sales",
    "app.domain.sales.order",
    "app.domain.shared",
    "app.domain.shared.barcode",
    "app.domain.shared.domain_event",
    "app.domain.shared.money",
    "app.infra",
    "app.infra.db",
    "app.infra.db.engine",
    "app.infra.db.migrations",
    "app.infra.db.models",
    "app.infra.db.triggers",
    "app.infra.hardware",
    "app.infra.hardware.base",
    "app.infra.hardware.registry",
    "app.infra.hardware.drivers",
    "app.infra.hardware.drivers.display",
    "app.infra.hardware.drivers.printer",
    "app.infra.hardware.drivers.scale",
    "app.infra.hardware.drivers.scanner",
    "app.infra.security",
    "app.infra.security.secrets",
    "app.infra.sync",
    "app.infra.sync.cloud_push",
    "app.infra.sync.daily_export",
    "app.kernel",
    "app.kernel.auth",
    "app.kernel.auth.engine",
    "app.kernel.events",
    "app.kernel.events.bus",
    "app.kernel.license",
    "app.kernel.license.fingerprint",
    "app.kernel.license.trial",
    "app.kernel.license.verifier",
]

# ── 排除模块 ──────────────────────────────────────────────────────
# 减小体积，排除不需要的库
EXCLUDES = [
    "tkinter",
    "PIL",
    "matplotlib",
    "IPython",
    "jupyter",
    "pytest",
    "setuptools",
    "pip",
    "_tkinter",
    "numpy",
    "scipy",
    "pandas",
    "pygments",
    "docutils",
    "sphinx",
    "tk",
    "Tcl",
    "turtle",
    "test",
    "unittest",
]

# ── 分析 ──────────────────────────────────────────────────────────
a = Analysis(
    [str(PROJECT_ROOT / "run.py")],  # 入口文件，绝对路径
    pathex=[str(PROJECT_ROOT)],        # 额外搜索路径，确保 import app 能找到
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ── PYZ ───────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ── EXE ───────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],                         # 单目录模式下此处不放入文件
    exclude_binaries=True,
    name="收银系统v3.2",         # 输出的 exe 文件名（不含扩展名）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                   # 使用 UPX 压缩（如果已安装）
    console=False,              # Windows GUI 模式，不显示终端窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=str(BUILD_ROOT / "软件源/icon.ico"),  # 如有自定义图标可取消注释
)

# ── COLLECT（单目录模式）─────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="收银系统v3.2",          # 输出的目录名
)

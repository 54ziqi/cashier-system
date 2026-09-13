# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['app.bootstrap', 'app.cli', 'app.lifecycle', 'fastapi', 'uvicorn', 'pydantic', 'sqlalchemy', 'bcrypt', 'cryptography', 'pydantic-settings']
hiddenimports += collect_submodules('app')


a = Analysis(
    ['../../run.py'],
    pathex=['/mnt/data/catpaw/home/workspace/收银系统'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='收银系统v3.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

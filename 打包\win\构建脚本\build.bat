@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM  柒号收银系统 v3.2 - Windows 构建脚本
REM  产物：PyInstaller 打包后的程序 + NSIS 安装包（.exe）
REM  发行签名：ZIQI
REM ============================================================

echo.
echo ============================================
echo   柒号收银系统 v3.2 - Windows 构建
echo   发布签名：ZIQI
echo   输出：安装包 (.exe)
echo ============================================
echo.

REM ── 1. 定位项目根目录 ──────────────────────────────────────
cd /d "%~dp0"
cd ..\..\..

set "PROJECT_ROOT=%CD%"
echo [1/5] 项目根目录: %PROJECT_ROOT%

REM ── 2. 检查 Python 版本 ────────────────────────────────────
echo.
echo [2/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请安装 Python 3.12+ 并确保在 PATH 中
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo         Python 版本: %PY_VER%

python -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)"
if errorlevel 1 (
    echo [错误] Python 版本过低，请使用 3.12+
    pause
    exit /b 1
)

echo         Python 版本检查通过

REM ── 3. 安装依赖 ────────────────────────────────────────────
echo.
echo [3/5] 安装 Python 依赖...
cd /d "%PROJECT_ROOT%"

if exist requirements.txt (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo [警告] requirements.txt 不存在，跳过依赖安装
)

pip install pyinstaller
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)
echo         依赖安装完成

REM ── 4. 执行 PyInstaller 构建 ──────────────────────────────
echo.
echo [4/5] 开始打包程序...

set "SPEC_DIR=%PROJECT_ROOT%\打包\win\构建脚本"
set "OUTPUT_DIR=%PROJECT_ROOT%\打包\win\输出"
set "WORK_DIR=%PROJECT_ROOT%\打包\win\构建日志\work"

if exist "%WORK_DIR%" rd /s /q "%WORK_DIR%"

cd /d "%SPEC_DIR%"

pyinstaller cashier.spec ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%PROJECT_ROOT%\打包\win" ^
    --noconfirm

if errorlevel 1 (
    echo [错误] PyInstaller 构建失败
    pause
    exit /b 1
)

echo         程序构建完成

REM ── 5. 生成安装包（NSIS） ──────────────────────────────────
echo.
echo [5/5] 生成 Windows 安装包...
where makensis >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 NSIS（makensis），请先安装 NSIS 并确保其在 PATH 中
    echo         参考：https://nsis.sourceforge.io/Download
    pause
    exit /b 1
)

cd /d "%SPEC_DIR%"
makensis installer.nsi
if errorlevel 1 (
    echo [错误] 安装包生成失败
    pause
    exit /b 1
)

echo         安装包生成完成

REM ── 6. 复制配置模板到输出目录 ─────────────────────────────
set "CONFIG_SRC=%PROJECT_ROOT%\打包\配置模板"
set "CONFIG_DST=%OUTPUT_DIR%\收银系统v3.2\config"

if not exist "!CONFIG_DST!" mkdir "!CONFIG_DST!"
copy /y "%CONFIG_SRC%\default.toml" "!CONFIG_DST!\" >nul
copy /y "%CONFIG_SRC%\lite.toml" "!CONFIG_DST!\" >nul

REM ── 完成 ──────────────────────────────────────────────────
echo.
echo ============================================
echo   构建完成！
echo   程序目录: %OUTPUT_DIR%\收银系统v3.2\
echo   安装包: %OUTPUT_DIR%\ZIQI-柒号收银系统-v3.2.0-Setup.exe
echo ============================================
echo.

pause
endlocal

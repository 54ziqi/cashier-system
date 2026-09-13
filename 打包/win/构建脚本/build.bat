@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM  柒号收银系统 v3.2 - Windows 构建脚本
REM  执行 build.bat，依赖 PyInstaller 打包为 exe
REM ============================================================

echo.
echo ============================================
echo   柒号收银系统 v3.2 - Windows 构建
echo ============================================
echo.

REM ── 1. 定位项目根目录 ──────────────────────────────────────
REM 本脚本位于: 打包/win/构建脚本/build.bat
REM 上溯两级到项目根目录
cd /d "%~dp0"                  REM 进入本脚本所在目录
cd ..\..\..                    REM 回到项目根目录

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

REM 检查版本是否 >= 3.8（宽松检查，实际需要 3.12+）
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
echo [4/5] 开始打包...

set "SPEC_DIR=%PROJECT_ROOT%\打包\win\构建脚本"
set "OUTPUT_DIR=%PROJECT_ROOT%\打包\win\输出"
set "WORK_DIR=%PROJECT_ROOT%\打包\win\构建日志\work"

REM 清理旧的构建缓存（保留 dist 给本次构建使用）
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

echo         构建完成

REM ── 5. 复制配置模板到输出目录 ─────────────────────────────
echo.
echo [5/5] 复制配置文件到输出目录...

set "CONFIG_SRC=%PROJECT_ROOT%\打包\配置模板"
set "CONFIG_DST=%OUTPUT_DIR%\收银系统v3.2\config"

if not exist "!CONFIG_DST!" mkdir "!CONFIG_DST!"
copy /y "%CONFIG_SRC%\default.toml" "!CONFIG_DST!\" >nul
copy /y "%CONFIG_SRC%\lite.toml" "!CONFIG_DST!\" >nul

echo         配置文件已复制

REM ── 完成 ──────────────────────────────────────────────────
echo.
echo ============================================
echo   构建完成！
echo   输出目录: %OUTPUT_DIR%\收银系统v3.2\
echo   可执行文件: %OUTPUT_DIR%\收银系统v3.2\收银系统v3.2.exe
echo ============================================
echo.

pause
endlocal

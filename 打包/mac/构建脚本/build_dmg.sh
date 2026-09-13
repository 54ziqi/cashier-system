#!/bin/bash
# ============================================================
#  柒号收银系统 v3.2.0 - macOS DMG 构建脚本
#  生成 .dmg 镜像，包含 .app Bundle
#  使用方式: cd 打包/mac/构建脚本 && bash build_dmg.sh
# ============================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo
echo "============================================"
echo "  柒号收银系统 v3.2.0 - macOS DMG 构建"
echo "============================================"
echo

# ── 1. 定位项目根目录 ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR: 打包/mac/构建脚本/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
# PROJECT_ROOT: 项目根目录

info "项目根目录: $PROJECT_ROOT"

# ── 2. 定义路径 ─────────────────────────────────────────────────
BUILD_ROOT="$PROJECT_ROOT/打包"
APP_NAME="柒号收银"
APP_BUNDLE="收银系统v3.2.app"
DMG_NAME="cashier-v3.2.0.dmg"
VOL_NAME="柒号收银系统 v3.2"

DIST_DIR="$BUILD_ROOT/mac/输出"
WORK_DIR="$BUILD_ROOT/mac/build_work"

# PyInstaller 中间产物临时目录
PYI_DIST="$WORK_DIR/dist"
PYI_BUILD="$WORK_DIR/build_file"

# ── 3. 检查 Python 版本 ────────────────────────────────────────
echo
info "检查 Python 环境..."

if ! command -v python3 &>/dev/null; then
    error "未检测到 python3，请安装 Python 3.12+"
fi

PY_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
info "Python 版本: $PY_VERSION"

# 检查版本 >= 3.8
python3 -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" || \
    error "Python 版本过低，请使用 3.12+"

success "Python 版本检查通过"

# ── 4. 安装依赖 ─────────────────────────────────────────────────
echo
info "安装 Python 依赖..."
cd "$PROJECT_ROOT"

if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
fi
pip3 install pyinstaller

success "依赖安装完成"

# ── 5. 清理旧的构建产物 ─────────────────────────────────────────
echo
info "清理旧构建产物..."
rm -rf "$WORK_DIR"
rm -rf "$DIST_DIR"
mkdir -p "$PYI_DIST"
mkdir -p "$PYI_BUILD"
mkdir -p "$DIST_DIR"

# ── 6. 构建 .app Bundle ─────────────────────────────────────────
echo
info "开始 PyInstaller 构建..."

cd "$PROJECT_ROOT"

pyinstaller \
    --name "收银系统v3.2" \
    --windowed \
    --distpath "$PYI_DIST" \
    --workpath "$PYI_BUILD" \
    --specpath "$SCRIPT_DIR" \
    --noconfirm \
    --clean \
    --osx-bundle-identifier "com.qihhao.cashier" \
    --add-data "$BUILD_ROOT/软件源/静态资源/html:static/html" \
    --add-data "$BUILD_ROOT/软件源/静态资源/css:static/css" \
    --add-data "$BUILD_ROOT/软件源/静态资源/js:static/js" \
    --add-data "$BUILD_ROOT/配置模板/default.toml:config/default.toml" \
    --add-data "$BUILD_ROOT/配置模板/lite.toml:config/lite.toml" \
    --hidden-import "fastapi" \
    --hidden-import "uvicorn" \
    --hidden-import "sqlalchemy" \
    --hidden-import "pydantic" \
    --hidden-import "pydantic_settings" \
    --hidden-import "bcrypt" \
    --hidden-import "cryptography" \
    --hidden-import "app.bootstrap" \
    --hidden-import "app.cli" \
    --hidden-import "app.config" \
    --hidden-import "app.lifespan" \
    --hidden-import "h11" \
    --hidden-import "starlette.routing" \
    --hidden-import "starlette.middleware.cors" \
    --hidden-import "starlette.staticfiles" \
    --hidden-import "sqlalchemy.orm" \
    --hidden-import "sqlalchemy.pool" \
    --exclude-module "tkinter" \
    --exclude-module "PIL" \
    --exclude-module "matplotlib" \
    --exclude-module "pytest" \
    --exclude-module "setuptools" \
    --exclude-module "pip" \
    run.py

success "PyInstaller 构建完成"

# ── 7. 复制额外的配置模板到 .app 内 ────────────────────────────
echo
info "将配置文件复制到 .app Bundle..."

APP_PATH="$PYI_DIST/$APP_BUNDLE"

# PyInstaller 已处理 --add-data，但双重确保配置文件存在
CONFIG_DST="$APP_PATH/Contents/Resources/config"
mkdir -p "$CONFIG_DST"
cp "$BUILD_ROOT/配置模板/default.toml" "$CONFIG_DST/default.toml" 2>/dev/null || true
cp "$BUILD_ROOT/配置模板/lite.toml"    "$CONFIG_DST/lite.toml"    2>/dev/null || true

# ── 8. 生成 Info.plist ──────────────────────────────────────────
echo
info "检查 Info.plist..."

PLIST_PATH="$APP_PATH/Contents/Info.plist"

if [ ! -f "$PLIST_PATH" ]; then
    # PyInstaller 没有生成则手动写入
    cat > "$PLIST_PATH" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>柒号收银</string>
    <key>CFBundleDisplayName</key>
    <string>柒号收银系统</string>
    <key>CFBundleIdentifier</key>
    <string>com.qihhao.cashier</string>
    <key>CFBundleVersion</key>
    <string>3.2.0</string>
    <key>CFBundleShortVersionString</key>
    <string>3.2.0</string>
    <key>CFBundleExecutable</key>
    <string>收银系统v3.2</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>CFBundleDocumentTypes</key>
    <array/>
</dict>
</plist>
PLIST_EOF
    info "已手动创建 Info.plist"
else
    info "PyInstaller 已生成 Info.plist"
fi

# ── 9. 创建 DMG 镜像 ────────────────────────────────────────────
echo
info "创建 DMG 镜像..."

DMG_TEMP="$WORK_DIR/temp.dmg"
MOUNT_POINT="/tmp/cashier_dmg_mount"

# 计算大致所需空间 (MB)
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$(( APP_SIZE + 50 ))  # 预留 50MB 额外空间

# 创建临时空白 DMG
hdiutil create \
    -size "${DMG_SIZE}m" \
    -volname "$VOL_NAME" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDRW \
    "$DMG_TEMP"

# 挂载 DMG
mkdir -p "$MOUNT_POINT"
hdiutil attach "$DMG_TEMP" -mountpoint "$MOUNT_POINT" -nobrowse

# 复制 .app Bundle 到 DMG
cp -R "$APP_PATH" "$MOUNT_POINT/"

# 创建"应用程序"文件夹的别名（让用户拖放安装）
ln -s /Applications "$MOUNT_POINT/Applications"

# 创建 DS_Store（简单可见性设置，可自定义背景图等）
# 此处保持最简单的布局

# 卸载 DMG
hdiutil detach "$MOUNT_POINT" -quiet

# 转换为压缩的只读 DMG
DMG_FINAL="$DIST_DIR/$DMG_NAME"
rm -f "$DMG_FINAL"
hdiutil convert "$DMG_TEMP" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_FINAL"

# 清理临时文件
rm -f "$DMG_TEMP"
rm -rf "$MOUNT_POINT"

success "DMG 镜像创建完成: $DMG_FINAL"

# ── 10. 完成 ────────────────────────────────────────────────────
echo
echo "============================================"
echo -e "${GREEN}构建完成！${NC}"
echo "  输出文件: $DMG_FINAL"
echo "  .app 位置: $APP_PATH"
echo "============================================"
echo

#!/usr/bin/env bash
# ============================================================================
# 柒号收银系统 - Tauri 一键构建脚本
# 用途: 构建 Tauri 桌面应用（macOS / Windows）
# 产物输出到: 打包/win/tauri/输出/
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/输出"
LOG_FILE="${SCRIPT_DIR}/build_$(date +%Y%m%d_%H%M%S).log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*" | tee -a "$LOG_FILE"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; }

# ============================================================================
# 1. 前置条件检查
# ============================================================================
log_info "检查前置条件..."

# 检查 Rust/Cargo
if ! command -v cargo &> /dev/null; then
    log_error "未找到 cargo，请先安装 Rust: https://rustup.rs/"
    exit 1
fi
RUST_VERSION=$(rustc --version)
log_info "Rust 版本: ${RUST_VERSION}"

# 检查 Cargo Tauri CLI
if ! cargo install --list 2>/dev/null | grep -q "tauri-cli"; then
    log_warn "未找到 cargo-tauri，正在安装..."
    cargo install tauri-cli@2 --force 2>&1 | tee -a "$LOG_FILE"
fi

# 检查 Node.js（用于前端资源）
if ! command -v node &> /dev/null; then
    log_warn "未找到 Node.js，Tauri 构建可能受限"
else
    NODE_VERSION=$(node --version)
    log_info "Node.js 版本: ${NODE_VERSION}"
fi

# ============================================================================
# 2. 确定构建目标
# ============================================================================
PLATFORM=$(uname -s)
ARCH=$(uname -m)

case "${PLATFORM}" in
    Darwin)
        if [ "${ARCH}" = "arm64" ]; then
            TARGET="universal-apple-darwin"
            log_info "构建目标: macOS (universal-apple-darwin)"
        else
            TARGET="x86_64-apple-darwin"
            log_info "构建目标: macOS (x86_64-apple-darwin)"
        fi
        ;;
    Linux)
        TARGET="x86_64-unknown-linux-gnu"
        log_info "构建目标: Linux (x86_64)"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        TARGET="x86_64-pc-windows-msvc"
        log_info "构建目标: Windows (x86_64-pc-windows-msvc)"
        ;;
    *)
        log_warn "未知平台 ${PLATFORM}，默认使用 x86_64-unknown-linux-gnu"
        TARGET="x86_64-unknown-linux-gnu"
        ;;
esac

# 检查目标是否已安装
if ! rustup target list --installed 2>/dev/null | grep -q "${TARGET}"; then
    log_info "安装编译目标: ${TARGET}"
    rustup target add "${TARGET}" 2>&1 | tee -a "$LOG_FILE"
fi

# ============================================================================
# 3. 准备产物输出目录
# ============================================================================
mkdir -p "${OUTPUT_DIR}"
log_info "输出目录: ${OUTPUT_DIR}"

# ============================================================================
# 4. 执行构建
# ============================================================================
log_info "开始 Tauri 构建..."
cd "${SCRIPT_DIR}/src-tauri"

cargo tauri build --target "${TARGET}" 2>&1 | tee -a "$LOG_FILE"

BUILD_EXIT=${PIPESTATUS[0]}

if [ ${BUILD_EXIT} -ne 0 ]; then
    log_error "Tauri 构建失败，退出码: ${BUILD_EXIT}"
    log_error "请查看日志: ${LOG_FILE}"
    exit ${BUILD_EXIT}
fi

# ============================================================================
# 5. 复制产物到输出目录
# ============================================================================
log_info "构建成功，复制产物..."

# 查找构建产物目录
BUILD_DIR="${SCRIPT_DIR}/src-tauri/target/${TARGET}/release/bundle"

if [ -d "${BUILD_DIR}" ]; then
    cp -r "${BUILD_DIR}"/* "${OUTPUT_DIR}/" 2>/dev/null || true
    log_info "已复制 bundle 产物"
fi

# 复制 sidecar 如果存在
SIDECAR_SRC="${PROJECT_ROOT}/打包/win/输出/收银系统sidecar"
if [ -f "${SIDECAR_SRC}" ]; then
    cp "${SIDECAR_SRC}" "${OUTPUT_DIR}/"
    log_info "已复制 Python sidecar"
fi

# ============================================================================
# 6. 汇总
# ============================================================================
log_info "============================================"
log_info "构建完成!"
log_info "输出目录: ${OUTPUT_DIR}"
log_info "日志文件: ${LOG_FILE}"
echo ""
ls -la "${OUTPUT_DIR}/" 2>/dev/null | tee -a "$LOG_FILE"
log_info "============================================"

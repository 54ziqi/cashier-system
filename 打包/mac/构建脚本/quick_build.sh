#!/bin/bash
# ============================================================
#  柒号收银系统 v3.2.0 - macOS 一键构建脚本
#  调用 build_dmg.sh，方便终端执行
#  使用方式: cd 打包/mac/构建脚本 && bash quick_build.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo
echo "============================================"
echo "  柒号收银系统 v3.2.0 - macOS 一键构建"
echo "============================================"
echo
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# 执行主构建脚本
bash "$SCRIPT_DIR/build_dmg.sh"
BUILD_RESULT=$?

echo
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"

if [ $BUILD_RESULT -eq 0 ]; then
    echo
    echo "============================================"
    echo "  构建成功！"
    echo "  请在 打包/mac/输出/ 目录查看 .dmg 文件"
    echo "============================================"
else
    echo
    echo "============================================"
    echo "  构建失败，请查看上方错误信息"
    echo "============================================"
fi

exit $BUILD_RESULT

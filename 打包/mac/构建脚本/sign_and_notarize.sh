#!/bin/bash
# ============================================================
#  柒号收银系统 v3.2.0 - macOS 签名 + 公证脚本
#  使用方式: bash sign_and_notarize.sh <path_to_dmg>
# ============================================================

set -euo pipefail

# 配置项 (用户需替换为真实数据)
CASHIER_VERSION="3.2.0"
APP_NAME="收银系统"
BUNDLE_ID="com.qihhao.cashier"
DEVELOPER_ID_APPLICATION="Developer ID Application: Your Name (TEAMID)"
DEVELOPER_ID_INSTALLER="Developer ID Installer: Your Name (TEAMID)"
APPLE_ID="your@email.com"
NOTARY_PASSWORD="@keychain:AC_PASSWORD"
TEAM_ID="YOURTEAMID"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── 配置校验 ────────────────────────────────────────────
validate_config() {
    local has_error=0

    if [[ "$DEVELOPER_ID_APPLICATION" == *"Your Name"* || "$DEVELOPER_ID_APPLICATION" == *"TEAMID"* ]]; then
        echo "⚠️  DEVELOPER_ID_APPLICATION 未配置，请替换为真实的证书名称"
        has_error=1
    fi

    if [[ "$DEVELOPER_ID_INSTALLER" == *"Your Name"* || "$DEVELOPER_ID_INSTALLER" == *"TEAMID"* ]]; then
        echo "⚠️  DEVELOPER_ID_INSTALLER 未配置，请替换为真实的证书名称"
        has_error=1
    fi

    if [[ "$APPLE_ID" == *"your@email"* ]]; then
        echo "⚠️  APPLE_ID 未配置，请替换为真实的 Apple ID"
        has_error=1
    fi

    if [[ "$TEAM_ID" == *"YOURTEAMID"* ]]; then
        echo "⚠️  TEAM_ID 未配置，请替换为真实的 Team ID"
        has_error=1
    fi

    if [[ $has_error -ne 0 ]]; then
        echo ""
        echo "❌ 配置项未就绪，请编辑本脚本顶部的配置项后重新运行"
        echo "   参考 README.md 获取详细配置说明"
        exit 2
    fi
}

# ─── 1. 参数检查 ─────────────────────────────────────────
DMG_PATH="${1:-}"
if [[ -z "$DMG_PATH" ]]; then
    echo "用法: bash sign_and_notarize.sh <path_to_dmg>"
    echo ""
    echo "示例:"
    echo "  bash sign_and_notarize.sh \"收银系统_v3.2.0.dmg\""
    echo "  bash sign_and_notarize.sh \"/Volumes/Build/收银系统.dmg\""
    exit 1
fi

# 支持相对路径转换
if [[ ! "$DMG_PATH" = /* ]]; then
    DMG_PATH="$SCRIPT_DIR/$DMG_PATH"
fi

if [[ ! -f "$DMG_PATH" ]]; then
    echo "❌ 错误: DMG 文件不存在: $DMG_PATH"
    exit 1
fi

# ─── 前置依赖检查 ─────────────────────────────────────────
check_dependencies() {
    local has_error=0

    if ! command -v xcrun &>/dev/null; then
        echo "❌ xcrun 未找到，请安装 Xcode 或 Xcode Command Line Tools"
        echo "   安装命令: xcode-select --install"
        has_error=1
    fi

    if ! command -v codesign &>/dev/null; then
        echo "❌ codesign 未找到"
        has_error=1
    fi

    if ! command -v hdiutil &>/dev/null; then
        echo "❌ hdiutil 未找到"
        has_error=1
    fi

    if [[ $has_error -ne 0 ]]; then
        exit 3
    fi

    # 检查证书是否存在
    if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "$DEVELOPER_ID_APPLICATION"; then
        echo "⚠️  代码签名证书未在 Keychain 中找到: $DEVELOPER_ID_APPLICATION"
        echo "   可用的签名身份:"
        security find-identity -v -p codesigning 2>/dev/null || true
        echo ""
        echo "   请确保证书已导入 Keychain Access"
    fi

    if ! security find-identity -v -p basic 2>/dev/null | grep -q "$DEVELOPER_ID_INSTALLER"; then
        echo "⚠️  DMG 签名证书未在 Keychain 中找到: $DEVELOPER_ID_INSTALLER"
    fi
}

# ─── 2. 签名嵌套 .app → .dmg ────────────────────────────
codesign_app() {
    echo "[1/5] 签名嵌套 .app Bundle..."

    local dmg_mount
    dmg_mount=$(hdiutil attach "$DMG_PATH" -readonly | grep "/Volumes/" | awk '{print $3}')

    if [[ -z "$dmg_mount" ]]; then
        echo "   ❌ DMG 挂载失败"
        return 1
    fi

    # 找到 .app
    local app_path=""
    for item in "$dmg_mount"/*.app; do
        if [[ -d "$item" ]]; then
            app_path="$item"
            break
        fi
    done

    if [[ -z "$app_path" ]]; then
        echo "   ⚠️  DMG 内未找到 .app Bundle，跳过嵌套签名"
        hdiutil detach "$dmg_mount" -quiet
        return 0
    fi

    echo "   📦 找到 .app: $(basename "$app_path")"

    # 检查 entitlements 文件位置
    local ent_path="$SCRIPT_DIR/entitlements.plist"
    if [[ ! -f "$ent_path" ]]; then
        # 向上查找
        ent_path="$(cd "$SCRIPT_DIR/../.." && pwd)/entitlements.plist"
        if [[ ! -f "$ent_path" ]]; then
            echo "   ⚠️  entitlements.plist 未找到，尝试默认路径"
            ent_path="$SCRIPT_DIR/entitlements.plist"
        fi
    fi

    local ent_args=()
    if [[ -f "$ent_path" ]]; then
        ent_args=(--entitlements "$ent_path")
        echo "   📋 使用 entitlements: $ent_path"
    else
        echo "   ⚠️  entitlements.plist 缺失，签名不包含 entitlements"
    fi

    # 签名 .app
    codesign --deep --force --verify --verbose=2 \
        --options runtime \
        --sign "$DEVELOPER_ID_APPLICATION" \
        "${ent_args[@]}" \
        "$app_path"

    echo "   ✅ .app Bundle 签名完成: $(basename "$app_path")"
    hdiutil detach "$dmg_mount" -quiet
}

# ─── 3. 签名 DMG 镜像 ────────────────────────────────────
codesign_dmg() {
    echo "[2/5] 签名 DMG 镜像..."
    codesign --force --verify --verbose=2 \
        --sign "$DEVELOPER_ID_INSTALLER" \
        --timestamp \
        "$DMG_PATH"
    echo "   ✅ DMG 签名完成"
}

# ─── 4. 提交公证 ─────────────────────────────────────────
notarize_dmg() {
    echo "[3/5] 提交公证..."

    # 检查是否已经公证过
    if xcrun stapler validate "$DMG_PATH" 2>/dev/null; then
        echo "   📌 已公证，跳过"
        return 0
    fi

    echo "   📤 提交公证请求..."

    # 提交公证
    local submit_output
    submit_output=$(xcrun notarytool submit "$DMG_PATH" \
        --apple-id "$APPLE_ID" \
        --password "$NOTARY_PASSWORD" \
        --team-id "$TEAM_ID" \
        --wait 2>&1)

    echo "$submit_output"

    # 提取 RequestUUID —— 先尝试从 info 获取
    local request_uuid
    request_uuid=$(echo "$submit_output" | grep -i "id:" | head -1 | awk '{print $2}')

    if [[ -z "$request_uuid" ]]; then
        echo "   ❌ 公证提交失败，无法获取 RequestUUID"
        echo "   完整输出:"
        echo "$submit_output"
        return 1
    fi

    echo "   ⏳ 公证审核中 (RequestUUID: $request_uuid)..."

    # 等待审核（轮询，备用机制 --wait 已经尝试等待了）
    local max_wait=600
    local waited=0
    local final_status=""

    while [[ $waited -lt $max_wait ]]; do
        sleep 10
        waited=$((waited + 10))

        local status_output
        status_output=$(xcrun notarytool info "$request_uuid" \
            --apple-id "$APPLE_ID" \
            --password "$NOTARY_PASSWORD" \
            --team-id "$TEAM_ID" 2>&1)

        local status
        status=$(echo "$status_output" | grep -i "Status:" | awk '{print $2}')

        case "$status" in
            "Accepted")
                echo "   ✅ 公证通过!"
                final_status="Accepted"
                break
                ;;
            "Invalid")
                echo "   ❌ 公证未通过"
                echo ""
                echo "   ── 公证日志 ────────────────────"
                echo "$status_output"
                echo "   ────────────────────────────────"
                echo ""
                echo "   查看详细日志 (需替换 RequestUUID):"
                echo "   xcrun notarytool log $request_uuid --apple-id \"$APPLE_ID\" --password \"$NOTARY_PASSWORD\" --team-id \"$TEAM_ID\""
                return 1
                ;;
            "In Progress")
                echo "     ⏳ 审核中... (${waited}s / ${max_wait}s)"
                ;;
            *)
                echo "     ⚠️  异常状态: $status (等待重试...)"
                ;;
        esac
    done

    if [[ "$final_status" != "Accepted" ]]; then
        echo "   ❌ 公证超时 (${max_wait}s)"
        echo "   稍后手动查询:"
        echo "   xcrun notarytool info $request_uuid --apple-id \"$APPLE_ID\" --password \"$NOTARY_PASSWORD\" --team-id \"$TEAM_ID\""
        return 1
    fi

    return 0
}

# ─── 5. 盖章 ─────────────────────────────────────────────
stapler_seal() {
    echo "[4/5] 盖章 (Stapler)..."

    # 确保 DMG 已签名
    if ! xcrun stapler validate "$DMG_PATH" 2>/dev/null; then
        xcrun stapler staple "$DMG_PATH"
        echo "   ✅ 盖章完成"
    else
        echo "   📌 已盖章，跳过"
    fi
}

# ─── 6. 最终验证 ─────────────────────────────────────────
final_verify() {
    echo "[5/5] 最终验证..."

    verify_pass=0

    echo "   📌 stapler validate:"
    if xcrun stapler validate "$DMG_PATH" 2>&1; then
        echo "      ✅ stapler 通过"
        verify_pass=$((verify_pass + 1))
    else
        echo "      ❌ stapler 失败"
    fi

    echo "   📌 codesign --verify:"
    if codesign --verify --deep --strict --verbose=2 "$DMG_PATH" 2>&1; then
        echo "      ✅ codesign 通过"
        verify_pass=$((verify_pass + 1))
    else
        echo "      ❌ codesign 失败"
    fi

    echo "   📌 spctl 安全评估:"

    # spctl 对 DMG 可能报错，attach 后再验证比较合理
    local spctl_output
    spctl_output=$(spctl --assess --type open --context context:primary-signature -v "$DMG_PATH" 2>&1) || true
    if echo "$spctl_output" | grep -q "accepted"; then
        echo "      ✅ spctl 通过"
        verify_pass=$((verify_pass + 1))
    else
        echo "      ⚠️  spctl 无 accepted 标记 (可能不影响分发)"
    fi

    echo ""
    if [[ $verify_pass -ge 2 ]]; then
        echo "✅ 全部完成: $(basename "$DMG_PATH") 签名 + 公证 + 盖章通过"
        echo ""
        echo "   文件路径: $DMG_PATH"
        echo "   文件大小: $(du -h "$DMG_PATH" | awk '{print $1}')"
    else
        echo "⚠️ 验证未完全通过，请检查上方日志"
        return 1
    fi
}

# ─── 主流程 ───────────────────────────────────────────────
main() {
    echo "============================================"
    echo "  柒号收银系统 v${CASHIER_VERSION}"
    echo "  macOS 签名 + 公证"
    echo "============================================"
    echo ""
    echo "  DMG 文件: $DMG_PATH"
    echo ""

    validate_config
    check_dependencies

    codesign_app
    codesign_dmg
    notarize_dmg
    stapler_seal
    final_verify
}

main "$@"

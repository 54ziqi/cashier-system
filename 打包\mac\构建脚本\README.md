# 柒号收银系统 -  macOS 打包 & 签名指南

本文档说明如何为 柒号收银系统 v3.2.0 创建签名的 macOS DMG 镜像，使其可以分发给最终用户（绕过 Gatekeeper 警告）。

---

## 前置条件

### 1. 硬件 & OS

- macOS 13.0+ ( Ventura )
- Apple Silicon 或 Intel Mac

### 2. Xcode / CLT

```bash
xcode-select --install
```

### 3. Apple Developer Program 会员 ($99/年)

注册地址: https://developer.apple.com/programs/

需要以下证书（在 [Apple Developer Portal](https://developer.apple.com/account/resources/certificates/list) 申请）：

| 证书类型 | 用途 | Keychain 中的名称 |
|---------|------|-------------------|
| Developer ID Application | 签名嵌套 .app | Developer ID Application: XYZ (TEAMID) |
| Developer ID Installer | 签名 DMG 镜像 | Developer ID Installer: XYZ (TEAMID) |

### 4. App-Specific Password (专用密码)

在 https://appleid.apple.com 生成:

1. 登录 Apple ID
2. "安全" → "App 专用密码"
3. 生成后填入脚本 `NOTARY_PASSWORD` 字段

或使用 Keychain Access 存储:

```bash
xcrun notarytool store-credentials "AC_PASSWORD" \
    --apple-id "your@email.com" \
    --team-id "YOURTEAMID"
```

然后脚本中 `NOTARY_PASSWORD="@keychain:AC_PASSWORD"` 这样使用。

---

## 目录结构

```
打包/mac/构建脚本/
├── INFO.plist                 # .app 元数据
├── build_dmg.sh               # 未签名 DMG 构建脚本
├── quick_build.sh             # 快速构建入口
├── sign_and_notarize.sh       # 签名 + 公证 + 盖章 (本指南)
└── entitlements.plist         # macOS sandbox entitlements
```

---

## 使用方式

### Step 1: 编辑配置

打开 `sign_and_notarize.sh`，修改顶部配置项:

```bash
# 替换为你自己的数据
DEVELOPER_ID_APPLICATION="Developer ID Application: 你的姓名 (TEAMID)"
DEVELOPER_ID_INSTALLER="Developer ID Installer: 你的姓名 (TEAMID)"
APPLE_ID="你的@email.com"
NOTARY_PASSWORD="@keychain:AC_PASSWORD"
TEAM_ID="你的TEAMID"
```

查看已有证书名称:

```bash
security find-identity -v -p codesigning
security find-identity -v -p basic
```

查看 Team ID:

```bash
# 在 Apple Developer Portal 查看
# 或运行: appleid:// 查看账户信息
```

### Step 2: 构建未签名 DMG

先使用 `build_dmg.sh` 生成未签名的 DMG:

```bash
bash build_dmg.sh
```

### Step 3: 签名 + 公证

```bash
bash sign_and_notarize.sh 收银系统_v3.2_0.dmg
```

完整输出示例:

```
============================================
  柒号收银系统 v3.2.0
  macOS 签名 + 公证
============================================

  DMG 文件: /path/to/收银系统_v3.2_0.dmg

[1/5] 签名嵌套 .app Bundle...
   📦 找到 .app: 收银系统.app
   📋 使用 entitlements: /path/to/entitlements.plist
   ✅ .app Bundle 签名完成: 收银系统.app
[2/5] 签名 DMG 镜像...
   ✅ DMG 签名完成
[3/5] 提交公证...
   📤 提交公证请求...
   ⏳ 公证审核中 (RequestUUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)...
     ⏳ 审核中... (30s / 600s)
     ⏳ 审核中... (60s / 600s)
   ✅ 公证通过!
[4/5] 盖章 (Stapler)...
   ✅ 盖章完成
[5/5] 最终验证...
   📌 stapler validate:      ✅ stapler 通过
   📌 codesign --verify:      ✅ codesign 通过
   📌 spctl 安全评估:         ⚠️  spctl 无 accepted 标记

✅ 全部完成: 收银系统_v3.2_0.dmg 签名 + 公证 + 盖章通过
```

---

## 公证常见周期

| 项目 | 时长 |
|------|------|
| 首次公证 | 可能需 24-48 小时审核 |
| 后续更新 | 3-10 分钟 |
| 超时设置 | 脚本内 `max_wait=600` (10 分钟) |

---

## 常见错误处理

### 1. `errSecInternalComponent` — Keychain 锁定

```bash
security unlock-keychain -p "你的登录密码" ~/Library/Keychains/login.keychain
```

### 2. `ERROR ITMS-xxxx` (旧 altool 已废弃)

这是旧版 `altool` 上传错误。本脚本已使用新版 `notarytool`，不会出现此问题。

如遇类似问题，确认 Xcode 版本 >= 13.0 (notarytool 从 Xcode 13 开始提供)。

### 3. Invalid 公证结果

下载详细日志:

```bash
xcrun notarytool log <RequestUUID> \
    --apple-id "your@email.com" \
    --password "@keychain:AC_PASSWORD" \
    --team-id "YOURTEAMID" \
    developer_log.json
```

常见原因:
- entitlements 配置错误
- 嵌套 Framework 未正确签名
- 使用了已废弃的 API

### 4. `spctl` 出现 "rejected"

通常是 debug 权限未注入或签名链不完整，使用 `codesign --verify --deep --strict` 定位问题。

### 5. DMG Gatekeeper 仍报 "Apple 无法检查是否包含恶意软件"

原因: 公证未成功 (stapler 未盖章)。

重新盖章:

```bash
xcrun stapler staple 收银系统_v3.2_0.dmg
xcrun stapler validate 收银系统_v3.2_0.dmg
```

---

## 一行命令 (组合使用)

```bash
# 构建 → 签名 → 公证 一条龙
cd 打包/mac/构建脚本 && \
    bash build_dmg.sh && \
    bash sign_and_notarize.sh 收银系统_v3.2_0.dmg
```

# GitHub Actions 云端构建 APK 操作指南

> 一键构建柒号收银系统 Android APK，无需本地安装 Android SDK

---

## 工作原理

```
你的电脑                    GitHub 云端                    产物
┌──────────┐   push      ┌──────────────────────┐     ┌──────────┐
│ 项目代码  │ ──────────→ │ Ubuntu 容器            │ ──→ │ debug.apk│
│          │             │ 1. JDK 17             │     │ (可下载)  │
│          │             │ 2. Android SDK         │     └──────────┘
│          │             │ 3. Gradle 编译         │
│          │             │ 4. Chaquopy Python嵌入  │
└──────────┘             └──────────────────────┘
```

---

## 快速开始（3 步）

### 步骤 1：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名：`cashier-system`
3. **不要**勾选 Add a README / .gitignore（因为你本地已有项目）
4. 点击 Create repository

### 步骤 2：推送本地代码

```powershell
# 在项目根目录执行
cd "C:\Users\Administrator\Desktop\收银系统"

# 初始化仓库
git init
git add .
git commit -m "v3.3: 完整收银系统 + Android APK 构建工作流"

# 关联远程仓库（替换 YOUR_USERNAME）
git remote add origin https://github.com/YOUR_USERNAME/cashier-system.git

# 推送
git branch -M main
git push -u origin main
```

### 步骤 3：触发构建

推送后自动触发：
1. 访问 `https://github.com/YOUR_USERNAME/cashier-system/actions`
2. 等待工作流运行完成（约 10-15 分钟）
3. 点击构建任务 → Artifacts → 下载 `cashier-debug-apk`

---

## 手动触发构建

如果已推送过代码，想重新构建：
1. 访问仓库页面的 **Actions** 标签
2. 选择 **Build Cashier System APK** 工作流
3. 点击 **Run workflow** 按钮

---

## APK 下载与使用

### 下载构建产物

1. 构建完成后，在 Actions 页面点击任务
2. 滚动到底部 Artifacts 区域
3. 点击下载 `cashier-debug-apk`
4. 解压得到 `cashier-debug.apk`（或类似名称）

### 安装到手机

**方法 A：USB 连接**
```powershell
adb install -r cashier-debug.apk
```

**方法 B：直接传输**
- 将 APK 文件传到手机（微信/邮件/U盘）
- 在手机文件管理器中点击安装
- 如提示"未知来源"，请在设置中允许

### 启动应用后

1. APK 启动后自动启动 Python 后端服务
2. 应用内 WebView 加载本地 Web 界面
3. 自动进入试用模式（30 天）
4. 输入初始管理员密码登录

---

## 故障排查

### 构建失败：Chaquopy pip 下载慢

在工作流文件中已配置 Aliyun PyPI 镜像，如果仍慢，手动编辑 `.github/workflows/build-apk.yml` 中：
```yaml
- name: Build debug APK
  run: |
    cd 打包/apk
    ./gradlew assembleDebug --no-daemon
```

在 `app/build.gradle` 的 `python { pip { ... } }` 中添加：
```gradle
options "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple"
```

### 构建失败：SDK 组件下载失败

GitHub Actions 使用 Ubuntu + Google 服务器下载速度较快，偶尔失败可重试。多次失败则拆分步骤：
```yaml
- name: Install platforms
  run: sdkmanager "platforms;android-34" --sdk_root=$ANDROID_SDK_ROOT
  
- name: Install build-tools
  run: sdkmanager "build-tools;34.0.0" --sdk_root=$ANDROID_SDK_ROOT
  
- name: Install NDK
  run: sdkmanager "ndk;25.2.9519653" --sdk_root=$ANDROID_SDK_ROOT
```

### 本地没有 adb

直接传输 APK 文件到手机安装即可，无需 adb。

---

## APK 技术参数

| 参数 | 值 |
|------|-----|
| 包名 | `com.qihhao.pos` |
| 最低系统 | Android 8.0 (API 24) |
| 目标系统 | Android 14 (API 34) |
| 支持架构 | arm64-v8a / x86_64 |
| 预估大小 | 80-120 MB |
| License | 30 天试用（可更新） |

---

*操作版本: v1.0 · 2026-09-13*

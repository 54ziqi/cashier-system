# 柒号收银系统 Android APK 构建指南

> 创建日期：2026-09-13  
> 适用平台：Android 8.0+ (API 24+, ARM64/x86_64)  
> 应用大小：约 80-120MB（含 Python 运行时 + 业务代码）

---

## 一、架构概览

APK 使用 **Kotlin + Chaquopy (Python for Android)** 构建：

```
┌──────────────────────────────────┐
│  Android App (Kotlin)            │
│  ┌────────────────────────────┐  │
│  │ WebView (POS UI)           │  │
│  │ ↕ JS Bridge ↕              │  │
│  │ PythonServerService        │  │
│  │ ↕ Uvicorn ↕                │  │
│  │ FastAPI Backend (Python)   │  │
│  │ ↕ SQLite ↕                 │  │
│  │收银业务逻辑                  │  │
│  └────────────────────────────┘  │
│         Chaquopy Runtime         │
│    (嵌入式 Python 3.10+)         │
└──────────────────────────────────┘
```

---

## 二、构建环境要求

### 2.1 必须安装的工具

| 工具 | 版本 | 用途 | 安装状态 |
|------|------|------|----------|
| JDK | 17+ | Gradle/Kotlin 编译 | ✅ 已安装 |
| Android SDK | API 34 (compileSdk) | Android 平台库 | ⚠️ 部分 |
| Git | 任意 | 拉取/推送代码 | 待安装 |
| Gradle | 8.4 | 构建系统 | 自动下载 |

### 2.2 系统环境变量

```powershell
JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17
ANDROID_HOME=C:\Users\Administrator\AppData\Local\Android\Sdk
ANDROID_SDK_ROOT=%ANDROID_HOME%
```

---

## 三、本地构建步骤

### 步骤 1：进入项目根目录

```powershell
cd "C:\Users\Administrator\Desktop\收银系统"
```

### 步骤 2：确保 Android SDK 完整

需要以下 SDK 组件（通过 Android Studio SDK Manager 或 sdkmanager）：

- [x] platform-tools
- [ ] platforms;android-34  ← **缺失**
- [ ] build-tools;34.0.0    ← **缺失**
- [ ] ndk;25.2.9519653      ← **缺失**（Chaquopy 需要）
- [ ] cmake;3.22.1          ← **缺失**

### 步骤 3：构建 APK

```powershell
cd "打包\apk"
.\gradlew.bat assembleDebug
```

输出 APK 路径：`app\build\outputs\apk\debug\app-debug.apk`

### 步骤 4：安装到手机

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

---

## 四、当前环境状态

以下 SDK 组件已完成安装：

| 组件 | 状态 | 大小 |
|------|------|------|
| cmdline-tools | ✅ 已安装 | 37MB |
| platform-tools (adb/fastboot) | ✅ 已安装 | 5.9MB |
| platforms;android-34 | ❌ 未安装 | — |
| build-tools;34.0.0 | ❌ 未安装 | — |
| ndk;25.2.9519653 | ❌ 未安装 | — |
| cmake;3.22.1 | ❌ 未安装 | — |

### 安装缺失组件的方法

#### 方法 A：使用 Android Studio（推荐）
1. 安装 Android Studio：`winget install Google.AndroidStudio`
2. 打开 SDK Manager → SDK Platforms → 勾选 "Android 14.0 (API 34)"
3. SDK Tools → 勾选 "Build-Tools 34.0.0"、"NDK"、"CMake"
4. 点击 Apply 安装

#### 方法 B：使用 sdkmanager（命令行）
```powershell
$env:ANDROID_HOME = "C:\Users\Administrator\AppData\Local\Android\Sdk"
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17"
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:PATH"

sdkmanager "platforms;android-34" "build-tools;34.0.0" "ndk;25.2.9519653" "cmake;3.22.1" --sdk_root=$env:ANDROID_HOME
```

#### 方法 C：使用 GitHub Actions（无需本地 SDK）
见下文第五节

---

## 五、GitHub Actions 云端构建（推荐）

由于本地下载 Android SDK 从 Google 服务器速度极慢，**强烈建议使用 GitHub Actions 自动构建**。

### 5.1 创建工作流文件

在项目中创建 `.github/workflows/build-apk.yml`，内容如下：

```yaml
name: Build APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          
      - name: Setup Android SDK
        uses: android-actions/setup-android@v3
        
      - name: Accept licenses & install SDK
        run: |
          yes | sdkmanager --licenses
          sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;25.2.9519653" "cmake;3.22.1"
          
      - name: Build debug APK
        run: |
          cd 打包/apk
          ./gradlew assembleDebug
          
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: cashier-debug-apk
          path: 打包/apk/app/build/outputs/apk/debug/app-debug.apk
```

### 5.2 触发构建

1. 推送代码到 GitHub
2. 访问仓库的 Actions 标签
3. 等待构建完成（约 10-15 分钟）
4. 下载 APK 附件

---

## 六、APK 架构说明

### 支持的 ABI

| ABI | 设备类型 |
|-----|----------|
| arm64-v8a | 现代 Android 手机/平板（2018 年后） |
| x86_64 | Android 模拟器 |

> 构建 APK 时只包含这两个 ABI，APK 体积约 80-120MB

### 启动流程

1. `MainActivity` 启动 `PythonServerService`
2. `PythonServerService` 通过 `Bridge.startServer()` 初始化 Chaquopy
3. Python 端启动 uvicorn/FastAPI，监听 127.0.0.1:8000
4. `MainActivity` 中的 WebView 加载 `http://127.0.0.1:8000`
5. WebView 与 Python 后端通过 REST API 交互

### 硬件支持

| 硬件 | 驱动方式 | 状态 |
|------|----------|------|
| USB 串口打印机 | usb-serial-for-android | ✅ 已实现 |
| USB 扫码枪 | UsbManager | ✅ 已实现 |
| 蓝牙打印机 | BluetoothAdapter RFCOMM | ✅ 已实现 |
| USB 串口电子秤 | UsbManager | ✅ 已实现 |

---

## 七、问题与解决

### Q: sdkmanager 下载太慢怎么办？
A: 使用 GitHub Actions 或配置网络代理。

### Q: Chaquopy pip 安装 Python 包失败？
A: Chaquopy 在构建时会自动从 PyPI 下载预编译 wheel。如果 PyPI 慢，可在 `build.gradle` 中配置 Chaquopy 镜像：
```gradle
python {
    pip {
        options "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple"
    }
}
```

### Q: APK 体积过大？
A: 1) 只保留 arm64-v8a ABI；2) 开启 R8/ProGuard 混淆；3) 使用 App Bundle

---

## 八、相关文档

| 文档 | 路径 |
|------|------|
| 项目总设计 | `/收银系统完整设计与实现文档v3.2.md` |
| 云后台方案 | `/连锁云后台建设方案.md` |
| 打包说明 | `/打包/打包说明.md` |
| 启动说明 | `/启动说明与使用指南.md` |

---

*文档版本: v1.0 · 2026-09-13*

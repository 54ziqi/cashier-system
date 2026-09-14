# 柒号收银系统 - Tauri 桌面端

## Tauri 方案简介

柒号收银系统采用 **Tauri v2** 作为桌面端封装方案，将现有 Python 后端作为 sidecar 进程管理，WebView 加载现有纯 HTML/CSS/JS 前端。

### 对比 PyInstaller 的优势

| 特性 | Tauri v2 | PyInstaller |
|------|----------|-------------|
| **包体积** | ~10-15 MB（使用系统 WebView） | ~80-150 MB（打包完整 Python 运行时） |
| **启动速度** | 快（原生 WebView） | 慢（需解压 Python 运行时到临时目录） |
| **内存占用** | 低（共享系统 WebView 资源） | 高（独立 Python 解释器 + 依赖库） |
| **安全性** | 高（Rust 内存安全 + 沙箱隔离） | 中（纯 Python 运行时，无沙箱） |
| **跨平台** | macOS / Windows / Linux 统一代码 | 需分平台打包 |
| **系统集成** | 深度集成（托盘、通知、全局快捷键） | 有限 |
| **自动更新** | 内置 updater 插件 | 需自行实现 |
| **签名** | 原生支持代码签名 | 需外部工具 |

## 前置条件

### 必需工具

1. **Rust 工具链** (>= 1.70)
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. **Node.js** (>= 18)
   ```bash
   # 使用 nvm 或直接从 https://nodejs.org/ 安装
   ```

3. **Tauri CLI v2**
   ```bash
   cargo install tauri-cli@2
   # 或
   npm install -g @tauri-apps/cli@latest
   ```

### 平台特定依赖

#### macOS
- Xcode Command Line Tools: `xcode-select --install`

#### Windows
- Microsoft Visual Studio C++ 构建工具（MSVC）
- WebView2 Runtime（Windows 11 自带，Windows 10 需安装）

#### Linux
```bash
sudo apt install libwebkit2gtk-4.1-dev \
  build-essential curl wget libssl-dev \
  libgtk-3-dev libayatana-appindicator3-dev \
  librsvg2-dev
```

## 构建流程

### 开发模式（热重载）

```bash
cd 打包/win/tauri
cargo tauri dev
```

开发模式下，Tauri 会启动 sidecar 进程并在 WebView 中加载 `http://localhost:8000`。

### 生产构建

```bash
cd 打包/win/tauri
cargo tauri build
```

产物位置：
- macOS: `src-tauri/target/release/bundle/dmg/` 或 `.app`
- Windows: `src-tauri/target/release/bundle/msi/` 或 `.nsis`

或使用一键构建脚本：

```bash
./build_tauri.sh
```

产物将输出到 `打包/win/tauri/输出/` 目录。

## Python Sidecar 说明

### Sidecar 机制

Tauri 通过 `externalBin` 配置将 Python 编译后的可执行文件（sidecar）打包到应用资源目录中。

```
柒号收银.app/
├── Contents/
│   ├── MacOS/
│   │   └── qihhao-cashier          # Tauri 主进程 (Rust)
│   ├── Resources/
│   │   ├── 收银系统sidecar          # Python sidecar 进程
│   │   └── ...                     # 其他资源
│   └── ...
```

### Sidecar 通信

1. Tauri 启动后，`lib.rs` 中的 `setup` 钩子启动 sidecar 进程
2. Sidecar 以 `serve --port 8000` 参数启动 uvicorn 服务
3. WebView 加载 `http://localhost:8000` 访问后端 API
4. 主窗口关闭时，`on_window_event` 钩子优雅停止 sidecar

### Sidecar 构建要求

Python 后端需预先打包为独立可执行文件：

```bash
# 使用 PyInstaller 构建 sidecar
pyinstaller --onefile \
  --name 收银系统sidecar \
  --hidden-import app.cli \
  run.py
```

产物 `dist/收银系统sidecar` 需放置在 `打包/win/tauri/` 目录下（与 `src-tauri/` 同级）。

## 项目结构

```
打包/win/tauri/
├── package.json              # Node 依赖（仅 Tauri CLI）
├── build_tauri.sh            # 一键构建脚本
├── README.md                 # 本文件
└── src-tauri/
    ├── Cargo.toml            # Rust 依赖与项目配置
    ├── tauri.conf.json       # Tauri 应用配置
    ├── build.rs              # Tauri 构建脚本
    ├── capabilities/
    │   └── default.json      # Tauri v2 权限配置
    └── src/
        ├── main.rs           # Rust 入口
        └── lib.rs            # 核心逻辑（sidecar 管理）
```

## 注意事项

1. **端口冲突**：默认 sidecar 监听 8000 端口，如已占用需调整配置
2. **防多开**：`tauri-plugin-single-instance` 确保应用单实例运行
3. **CSP 策略**：`tauri.conf.json` 中已配置允许 `http://localhost:*` 访问
4. **图标**：需准备 `32x32.png`、`128x128.png`、`128x128@2x.png`、`icon.icns` 放入 `src-tauri/icons/`

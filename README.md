# Cashier · 轻量级离线收银系统

<p align="center">
  <b>Python 3.10+ / FastAPI / SQLite · 完全离线 · 硬件原生 · DDD 整洁架构</b>
</p>

一个面向小店、摊点、临时网点的离线优先收银系统。不依赖云服务、自带 RSA-PSS 授权与硬件指纹绑定，接扫码枪、电子秤、小票打印机即开箱即用。前端为零依赖原生 SPA，后端单进程可跑，数据存在本地 SQLite (WAL)。

---

## ✨ 特性

| 方向 | 做了什么 |
|------|---------|
| **离线优先** | RSA-PSS + AES-GCM License、硬件指纹绑定、完全无需公网 |
| **硬件原生** | 扫码枪 / 小票打印机 / 电子秤 / 客显收款码屏 —— 串口 + ESC/POS + QR |
| **收银链路** | 加入购物车 → 现金 / 余额 / 混合支付 → 小票打印 → 退款 CAS 原子化 |
| **商品 / 库存** | SKU / 条形码 / 称重 / 分类 / 库存低线预警 |
| **会员 / 余额** | 余额充值 (RBAC) / 积分 / 余额组合支付 |
| **Agent 旁路** | 商品推荐、异常检测、库存预警 —— 旁路不挡主收银流 |
| **API** | FastAPI + Pydantic v2、OpenAPI 文档 `/docs` |
| **前端** | 纯原生 HTML/JS/CSS SPA，无构建步骤 |
| **测试** | pytest + tmp SQLite DB、60 用例、覆盖鉴权/并发/退款/RBAC |
| **安全加固** | Token 撤销持久化、innerHTML XSS 清零、RBAC、LIKE 转义、Keydown 不拦输入框 |
| **UI 品质** | 玻璃质感面板、微交互动效 (CSS-only)、无障碍 focus-visible、`prefers-reduced-motion` 降级、打印小票样式 |

---

## 技术栈

| 层 | 选型 |
|----|------|
| 语言 | Python 3.10+ |
| Web 框架 | FastAPI + Uvicorn |
| 数据 | SQLAlchemy 2 + SQLite WAL + NullPool |
| 鉴权 | bcrypt + HMAC Session Token + 内存/DB 撤销列表 |
| 许可证 | RSA-PSS 签名 + AES-GCM 硬件指纹绑定 |
| 前端 | 原生 HTML5 / CSS3 / ES2020 (零依赖) |
| CLI | `cashier serve / init / license / backup / status` |
| 硬件 | pyserial / python-escpos / qrcode (可选) |

---

## 项目结构

```
.
├── app/
│   ├── kernel/        # 领域内核 (License / Auth / EventBus)
│   ├── domain/        # 聚合与值对象 (Order / Product / Member / Money / Barcode)
│   ├── application/   # 用例编排 (Checkout / Member / Payment / Product / Category)
│   ├── api/           # FastAPI 路由 (merchant / admin / auth / health)
│   ├── infra/         # 持久化、硬件驱动、密钥
│   ├── agents/        # 旁路 Agent (推荐 / 异常检测 / 库存预警)
│   ├── cli.py         # 命令行入口
│   └── lifespan.py    # 应用启动引导 (硬件即插即用)
├── static/            # 前端 SPA (js / css / index.html)
├── config/            # lite.toml / default.toml
├── tests/             # pytest 全量测试 (60 用例)
├── pyproject.toml
└── run.py             # 快捷启动: python run.py serve --profile lite
```

按 DDD 四层切分，领域层无框架依赖，应用层只编排，基础设施可替换。

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/54ziqi/cashier-system.git
cd cashier-system

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .[dev]             # 一并装可选硬件包用 .[hardware]
```

### 2. 初始化 & 生成试用 License

```bash
cashier init
cashier license --trial 30        # 若未放置商业 License 可先生成 30 天试用
```

数据默认落在 `~/.cashier/data/`，可在 `lite.toml` 调整路径。

### 3. 启动

```bash
cashier serve --profile lite      # 或  python run.py serve --profile lite
# 浏览器进入 http://127.0.0.1:8000
```

首次进入会看到登录页，账号密码见 `~/.cashier/data/initial-password.txt`；首次登录成功后会**自动删除该文件**。

### 4. 控制台命令总览

| 命令 | 作用 |
|------|------|
| `cashier serve --profile lite\|cloud` | 启动 HTTP 服务 |
| `cashier init` | 初次创建 DB / 目录 |
| `cashier license --trial N` | 生成 N 天试用 License |
| `cashier backup` | 热备份 SQLite |
| `cashier status` | 健康体检、硬件概览 |

---

## 运行测试

```bash
pytest -q
# 60 passed in ~15s
```

测试用临时 SQLite DB，每个用例独立事务、销毁重建，不会污染真实数据。覆盖面：鉴权引擎 / Token 撤销 / 并发库存防超卖 / 余额原子性 / 退款 CAS 状态机 / RBAC / 搜索转义 / API 集成。

---

## API 概览

启动后进入 `http://127.0.0.1:8000/docs` 得 Swagger UI。

| 前缀 | 主要功能 |
|------|---------|
| `/api/v1/auth` | 登录 / 登出 / Me / 当前用户 |
| `/api/v1/merchant/categories` | 分类 CRUD (RBAC) |
| `/api/v1/merchant/products` | 商品管理 / 搜索 (LIKE 转义) |
| `/api/v1/merchant/orders` | 创建订单 / 列表 / 退款 (CAS 原子化) |
| `/api/v1/merchant/cashier` | 会员充值 (RBAC) |
| `/api/v1/admin/tenants` | 多租户管理 (RBAC) |
| `/api/v1/admin/licenses` | License 管理 (RBAC) |
| `/health/ready` | 健康检查 (已脱敏) |

除登录 / 健康检查外, 所有端点都需携带 `Authorization: Bearer <token>`。涉及资金 (充值 / 退款) 的端点强制 `merchant_admin` 角色。

---

## 安全设计

- **Token 撤销持久化**：撤销即写库 (`revoked_tokens` 表)，重启保留。
- **RBAC**：所有资金接口强制 `merchant_admin` 角色。
- **XSS 清零**：全部前端渲染走 DOM API (`createElement` + `textContent`)，永不拼 `innerHTML`。
- **LIKE 转义**：搜索关键字中的 `%` `_` `\` 统一转义。
- **退款原子化**：CAS 状态变迁 `paid → refunding → refunded`，杜绝并发重复退款。
- **条码分支竞态保护**：POS 端加 race guard + 严格 EAN8/12/14 长度校验。
- **输入框不拦键盘**：全局 keydown 检测 `activeElement`，避免挡输入。

---

## 硬件

| 设备 | 协议/驱动 |
|------|----------|
| 扫码枪 | 串口字符流，支持 EAN/UPC，含 activeElement 防误触发 |
| 小票打印机 | ESC/POS，热敏，自动切刀 |
| 电子秤 | 串口称重商品实时取重 |
| 客显收款码屏 | QR Code (qrcode[pil]) |

全部旁路到 `app/infra/hardware/`，逻辑上可热插拔；未接入硬件时收银链路仍正常运转。

---

## License

本项目作技术演示与学习，商业 License 体系 (RSA-PSS + AES-GCM) 已内置，试用模式 30 天。

欢迎 issue / PR 一起打磨 🙌

---

*README 由项目维护者 ZIQI 撰写，从代码、测试、设计文档交叉校验生成。*

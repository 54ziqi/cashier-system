# 柒号收银系统 — 品牌设计规范 v2.0

> 三源合一。一份令牌，一套语法，统一 POS 收银台 / 报表 / 云端看板视觉语言。

---

## 1. 合并日志

| 来源 | 文件 | 令牌前缀 | 行数(约) | 处置 |
|------|------|----------|----------|------|
| legacy | `app.css` | `--c-*` / `--sp-*` / `--r-*` / `--shadow-*` | 57 行 | → **向后兼容别名**，指向 `--qh-*` 权威值 |
| v1 语义 | `brand.css` | `--qh-*` | 99 行 | → **权威命名**，全部保留并扩展 |
| v1 扩展 | `brand-extend.css` | `--color-*` / `--glass-*` / `--spacing-*` / `--radius-*` | 252 行 | → **语义重命名**为 `--qh-industry-*` / `--qh-order-*` / `--qh-glass-*` 等 |
| 动效 | `motion.css` | `--motion-*` | 52 行 | → **保留独立命名空间**，缓动/时长统一走 `--ease-*` / `--dur-*` |
| 组件 | `toast.css` / `notify.css` | `var(--qh-*)` | 0 | → 已接入，无需迁移 |

**合并结果**：~700 行碎片 → **1 个文件 / 300 行 / 单一名 `--qh-*` 权威层 + 一份完整向后兼容别名表**。

---

## 2. 命名规范速查表

```
--qh-ink-*        文字层级 (ink / ink-soft / ink-mute / ink-inverse)
--qh-bg-*         背景层级 (bg / bg-soft)
--qh-surface-*    卡片层级 (surface / surface-alt / surface-hover)
--qh-line-*       边框 (line / line-soft)
--qh-accent-*     品牌主色 (accent / accent-soft / accent-strong)
--qh-green-*      收银绿辅色 (green / green-light / green-strong)
--qh-success/warning/danger/info    语义色 (+ -bg / -text)
--qh-industry-*   行业扩展色 (fast-food / full-service / beverage / hotpot / bakery / retail)
--qh-order-*      订单状态色 (pending / paid / making / ready / served / completed / voided / refunded)
--qh-glass-*      玻璃拟态 (bg / bg-hover / border / blur / overlay)
--qh-space-*      间距 1-10 (4px→80px, 8pt 基准)
--qh-radius-*     圆角 sm/md/lg/xl/2xl/full
--qh-shadow-*     阴影 sm/md/lg/xl/glow
--qh-font-*       字号 xs/sm/base/md/lg/xl/2xl/3xl + 字族 sans/mono/num
--qh-chart-*      图表色板 1-7
--ease-*          缓动 (standard / out / in / emphasized / spring / snap)
--dur-*           时长 (fast / normal / slow / slower)
--motion-*        动效(保留 motion.css 原始命名)
--z-*             z-index 命名层
```

---

## 3. 语义化色彩速查

| 用途 | 亮色令牌值 | 暗色令牌值 |
|------|-----------|-----------|
| 一级文字 | `--qh-ink` #0F172A | `--qh-ink` #F1F5F9 |
| 次级文字 | `--qh-ink-soft` #475569 | `--qh-ink-soft` #CBD5E1 |
| 注释/占位 | `--qh-ink-mute` #94A3B8 | `--qh-ink-mute` #64748B |
| 页面底色 | `--qh-bg` #F1F5F9 | `--qh-bg` #0F172A |
| 卡片表面 | `--qh-surface` #FFFFFF | `--qh-surface` #1E293B |
| 悬浮态 | `--qh-surface-hover` #F1F5F9 | `--qh-surface-hover` #334155 |
| 分割线 | `--qh-line` #E2E8F0 | `--qh-line` #334155 |
| 主品牌色 | `--qh-accent` #0F172A | (同亮色) |
| 收银绿 | `--qh-green` #10B981 | (同亮色) |
| 成功 | `--qh-success` #059669 | (同亮色) |
| 警告 | `--qh-warning` #F59E0B | (同亮色) |
| 危险 | `--qh-danger` #DC2626 | (同亮色) |
| 信息 | `--qh-info` #0EA5E9 | (同亮色) |

### 语义色增值

| 语义 | 主色 | 浅底 | 深文 |
|------|------|------|------|
| success | `--qh-success` | `--qh-success-bg` | `--qh-success-text` |
| warning | `--qh-warning` | `--qh-warning-bg` | `--qh-warning-text` |
| danger | `--qh-danger` | `--qh-danger-bg` | `--qh-danger-text` |
| info | `--qh-info` | `--qh-info-bg` | `--qh-info-text` |

---

## 4. 间距/圆角/阴影 8pt 网格

### 间距阶梯

| Token | 值 | 用途 |
|-------|----|------|
| `--qh-space-1` | 4px | 紧凑内联间距 |
| `--qh-space-2` | 8px | 表单项间距 |
| `--qh-space-3` | 12px | 卡片内 padding-sm |
| `--qh-space-4` | 16px | 卡片内 padding-md |
| `--qh-space-5` | 20px | 区块间距 |
| `--qh-space-6` | 24px | 卡片内 padding-lg |
| `--qh-space-7` | 32px | 区段分隔 |
| `--qh-space-8` | 48px | 大区块间距 |
| `--qh-space-9` | 64px | 页面级间距 |
| `--qh-space-10`| 80px | 装饰性大间距 |

### 圆角阶梯

| Token | 值 | 用途 |
|-------|----|------|
| `--qh-radius-sm` | 6px | 按钮、输入框、Tag |
| `--qh-radius-md` | 10px | 小卡片、规格选项 |
| `--qh-radius-lg` | 14px | 数据卡片、选择器 |
| `--qh-radius-xl` | 20px | 大卡片、Modal |
| `--qh-radius-2xl`| 28px | Drawer、特殊容器 |
| `--qh-radius-full`| 9999px | 胶囊按钮、徽点 |

### 阴影阶梯

| Token | 值 | 用途 |
|-------|----|------|
| `--qh-shadow-sm` | 0 1px 2px rgba(15,23,42,.06) | 按钮、悬浮微升 |
| `--qh-shadow-md` | 0 4px 12px rgba(15,23,42,.08) | 卡片主体 |
| `--qh-shadow-lg` | 0 10px 30px rgba(15,23,42,.10) | Modal / Popover |
| `--qh-shadow-xl` | 0 24px 60px rgba(15,23,42,.14) | Drawer 弹窗 |
| `--qh-shadow-glow`| 0 0 24px rgba(16,185,129,.18) | KPI 渐变边框 / 收银确认 |

### 缓动与时长

| Token | 值 | 用途 |
|-------|----|------|
| `--ease-standard` | cubic-bezier(.4,0,.2,1) | 通用 |
| `--ease-out` | cubic-bezier(0,0,.2,1) | 入场 |
| `--ease-in` | cubic-bezier(.4,0,1,1) | 退场 |
| `--ease-emphasized` | cubic-bezier(.2,0,0,1) | 强调 |
| `--ease-spring` | cubic-bezier(.34,1.56,.64,1) | 微过冲弹回 |
| `--dur-fast` | 120ms | hover/active |
| `--dur-normal` | 200ms | 卡片切换 |
| `--dur-slow` | 350ms | 弹窗/drawer |
| `--dur-slower` | 600ms | 页面转场 |

---

## 5. 行业色/订单状态色

### 6 大行业品类色

| Token | 值 | 行业 |
|-------|----|------|
| `--qh-industry-fast-food` | #F59E0B | 快餐 |
| `--qh-industry-full-service` | #EF4444 | 正餐 |
| `--qh-industry-beverage` | #06B6D4 | 茶饮 |
| `--qh-industry-hotpot` | #F97316 | 火锅 |
| `--qh-industry-bakery` | #D946EF | 烘焙 |
| `--qh-industry-retail` | #10B981 | 零售 |

### 8 态订单闭环

| Token | 值 | 状态 |
|-------|----|------|
| `--qh-order-pending` | #94A3B8 | 待支付 |
| `--qh-order-paid` | #0EA5E9 | 已支付 |
| `--qh-order-making` | #F59E0B | 制作中 |
| `--qh-order-ready` | #10B981 | 待取餐 |
| `--qh-order-served` | #6366F1 | 已上餐 |
| `--qh-order-completed` | #22C55E | 已完成 |
| `--qh-order-voided` | #EF4444 | 作废 |
| `--qh-order-refunded` | #F97316 | 已退款 |

---

## 6. 玻璃拟态配方

玻璃效果 = 浅色底 + 模糊 + 半透明描边。

```css
.glass-card {
  background: var(--qh-glass-bg);           /* rgba(255,255,255,.72) */
  backdrop-filter: blur(var(--qh-glass-blur)); /* 12px */
  -webkit-backdrop-filter: blur(var(--qh-glass-blur));
  border: 1px solid var(--qh-glass-border);  /* rgba(255,255,255,.22) */
  border-radius: var(--qh-radius-lg);
  box-shadow: var(--qh-shadow-md);
}
```

暗色主题覆盖：

```css
body.theme-dark {
  --qh-glass-bg: rgba(255,255,255,.05);
  --qh-glass-bg-hover: rgba(255,255,255,.10);
  --qh-glass-border: rgba(255,255,255,.10);
}
```

---

## 7. 组件引用示例

### 数据卡片

```css
.card-kpi {
  background: var(--qh-surface);
  border-radius: var(--qh-radius-lg);
  box-shadow: var(--qh-shadow-md);
  padding: var(--qh-space-5) var(--qh-space-6);
  border: 1px solid var(--qh-line);
  font-family: var(--qh-font-sans);
  font-size: var(--qh-font-base);
  color: var(--qh-ink);
  transition: box-shadow var(--dur-normal) var(--ease-standard);
}
.card-kpi:hover {
  box-shadow: var(--qh-shadow-lg);
}
.kpi-value {
  font-family: var(--qh-font-num);
  font-size: var(--qh-font-2xl);
  font-weight: 700;
  color: var(--qh-accent);
  font-variant-numeric: tabular-nums;
}
```

### 收银按钮

```css
.btn-checkout {
  background: var(--qh-green);
  color: var(--qh-ink-inverse);
  border-radius: var(--qh-radius-sm);
  padding: var(--qh-space-3) var(--qh-space-6);
  font-size: var(--qh-font-md);
  font-weight: 600;
  transition: background var(--dur-fast) var(--ease-standard),
              transform var(--dur-fast) var(--ease-spring);
}
.btn-checkout:hover { background: var(--qh-green-strong); }
.btn-checkout:active { transform: scale(0.96); }
```

### 订单状态徽标

```css
.badge-order {
  display: inline-block;
  padding: 2px var(--qh-space-2);
  border-radius: var(--qh-radius-full);
  font-size: var(--qh-font-xs);
  font-weight: 600;
  background: var(--qh-info-bg);
  color: var(--qh-info-text);
}
.badge-order.making {
  background: var(--qh-warning-bg);
  color: var(--qh-warning-text);
}
```

---

## 8. 迁移策略

1. **Phase 1 — 无痛接入**：在 HTML 中用 `tokens-merged.css` 替换 `app.css` + `brand.css` + `brand-extend.css` 三行 link。所有旧变量通过别名自动生效，零破坏。
2. **Phase 2 — 渐进替换**：开发者在新代码中直接使用 `--qh-*`；老代码按需逐步替换 `--c-*`。
3. **Phase 3 — 清除别名**：确认所有文件迁移完毕后，删除 tokens-merged.css 中「向后兼容别名」区段，文件缩减至 ~150 行。

详见 `migrate-checklist.md`。

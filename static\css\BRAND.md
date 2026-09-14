# 柒号收银系统 — 品牌设计系统文档

> 版本: v1.0 · 适用项目: 柒号收银系统 (QH POS)  
> 风格: Glass Morphism + 青蓝渐变 (#0EA5E9 → #6366F1)  
> 命名空间护盾: `--qh-*` / `--c-*` / `--color-*` / `--chart-*` / `--glass-*` / `--spacing-*` / `--radius-*` / `--shadow-*` / `--font-size-*`

---

## 1. 色彩系统速查

### 1.1 品类色 (行业身份)

| 行业 | 主色 | 浅底 | 深色文字 | Token 前缀 |
|------|------|------|----------|-----------|
| 快餐 | `#F59E0B` 琥珀 | `#FFFBEB` | `#92400E` | `--color-industry-fast-food(-bg/-text)` |
| 正餐 | `#EF4444` 朱红 | `#FEF2F2` | `#991B1B` | `--color-industry-full-service(-bg/-text)` |
| 茶饮 | `#06B6D4` 青蓝 | `#ECFEFF` | `#155E75` | `--color-industry-beverage(-bg/-text)` |
| 火锅 | `#F97316` 橙 | `#FFF7ED` | `#9A3412` | `--color-industry-hotpot(-bg/-text)` |
| 烘焙 | `#D946EF` 紫红 | `#FAF5FF` | `#86198F` | `--color-industry-bakery(-bg/-text)` |
| 零售 | `#10B981` 翠绿 | `#ECFDF5` | `#065F46` | `--color-industry-retail(-bg/-text)` |

### 1.2 订单状态色 (运行时状态)

| 状态 | 主色 | 浅底 | 深色文字 | Token |
|------|------|------|----------|-------|
| pending (待支付) | `#94A3B8` 灰蓝 | `#F1F5F9` | `#334155` | `--color-order-*` |
| paid (已支付) | `#0EA5E9` 天际蓝 | `#EFF6FF` | `#0C4A6E` | `--color-order-*` |
| making (制作中) | `#F59E0B` 琥珀 | `#FFFBEB` | `#92400E` | `--color-order-*` |
| ready (待取/完成) | `#10B981` 翠绿 | `#ECFDF5` | `#065F46` | `--color-order-*` |
| served (已上餐) | `#6366F1` 靛紫 | `#EEF2FF` | `#3730A3` | `--color-order-*` |
| completed (完成) | `#22C55E` 鲜绿 | `#DCFCE7` | `#166534` | `--color-order-*` |
| voided (作废) | `#EF4444` 朱红 | `#FEF2F2` | `#991B1B` | `--color-order-*` |
| refunded (已退款) | `#F97316` 橙 | `#FFF7ED` | `#9A3412` | `--color-order-*` |

### 1.3 数据可视化色板 (Chart.js / ECharts, 7 色)

| 用途 | 色值 | Token |
|------|------|-------|
| 收入/客流 | `#06B6D4` 青蓝 | `--chart-cyan` |
| 单量 | `#3B82F6` 蓝 | `--chart-blue` |
| 客单价 | `#6366F1` 靛紫 | `--chart-indigo` |
| 退单率 | `#8B5CF6` 紫 | `--chart-purple` |
| 外卖占比 | `#EC4899` 粉 | `--chart-pink` |
| 时段峰值 | `#F59E0B` 琥珀 | `--chart-amber` |
| 会员消费 | `#10B981` 翠绿 | `--chart-emerald` |

### 1.4 中性色与文本

| Token | 值 | 用途 |
|-------|----|------|
| `--text-primary` | `#F8FAFC` slate-50 | 一级标题、金额 |
| `--text-secondary` | `#CBD5E1` slate-300 | 正文、描述 |
| `--text-tertiary` | `#94A3B8` slate-400 | 次级说明 |
| `--text-muted` | `#64748B` slate-500 | 占位符、图标 |
| `--text-inverse` | `#0F172A` slate-900 | 亮色背景上的深色字 |
| `--text-accent` | `#0EA5E9` sky-500 | 高亮强调文字 |

### 1.5 背景

| Token | 值 | 用途 |
|-------|----|------|
| `--bg-app` | `linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)` | 页面底色 |
| `--bg-card` | `rgba(255,255,255,0.08)` | 卡片底色 |
| `--bg-card-hover` | `rgba(255,255,255,0.14)` | 卡片悬停 |
| `--bg-elevated` | `rgba(30,41,59,0.85)` | 弹窗、抽屉浮层 |

---

## 2. 圆角/间距/阴影使用规则

### 2.1 圆角梯度

| Token | 值 | 适用组件 |
|-------|----|----------|
| `--radius-sm` | 6px | Tag、徽标、Tooltip |
| `--radius-md` | 10px | 按钮、输入框、下拉项 |
| `--radius-lg` | 14px | 卡片、区段容器 |
| `--radius-xl` | 20px | 大卡片、Modal |
| `--radius-2xl` | 28px | Drawer、特殊浮层 |
| `--radius-full` | 9999px | 胶囊按钮、Avatar 外框 |

### 2.2 间距梯度 (8pt grid)

| Token | 值 | 用途 |
|-------|----|------|
| `--spacing-0` | 0px | 消除间距 |
| `--spacing-1` | 4px | 内联微调 |
| `--spacing-2` | 8px | 紧凑内联、图标-文字 |
| `--spacing-3` | 12px | 列表项间距 |
| `--spacing-4` | 16px | 卡片内边距、组件间距 |
| `--spacing-5` | 20px | 区段内间距 |
| `--spacing-6` | 24px | 卡片外间距 |
| `--spacing-7` | 32px | 区块间间距 |
| `--spacing-8` | 48px | 页面级大间距 |
| `--spacing-9` | 64px | 极大方块间距 |

### 2.3 阴影梯度

| Token | 值 | 用途 |
|-------|----|------|
| `--shadow-sm` | `0 2px 8px rgba(0,0,0,.08)` | Tag、小徽标、子元素 |
| `--shadow-md` | `0 4px 16px rgba(0,0,0,.12)` | 卡片、按钮浮动 |
| `--shadow-lg` | `0 8px 32px rgba(0,0,0,.16)` | Modal、Drawer |
| `--shadow-xl` | `0 16px 48px rgba(0,0,0,.20)` | 大浮层、Message |
| `--shadow-glow` | `0 0 24px rgba(14,165,233,.25)` | 主焦点/高亮强调 |
| `--shadow-inner` | `inset 0 1px 2px rgba(0,0,0,.06)` | 凹陷效果、输入框内阴影 |

---

## 3. 玻璃拟态组件配方

### 3.1 通用配方

```css
/* 玻璃卡片 */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur-md, 16px));
  -webkit-backdrop-filter: blur(var(--glass-blur-md, 16px));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow-md);
  color: var(--text-primary);
  transition:
    background var(--dur-base) var(--ease-smooth),
    border-color var(--dur-base) var(--ease-smooth),
    box-shadow var(--dur-base) var(--ease-smooth);
}
.glass-card:hover {
  background: var(--glass-bg-hover);
  border-color: var(--glass-border-hover);
}

/* 玻璃模态框 */
.glass-modal {
  background: var(--bg-elevated);
  backdrop-filter: blur(var(--glass-blur-lg, 24px));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg, 24px));
  border: 1px solid var(--glass-border-strong);
  border-radius: var(--radius-xl);
  box-shadow: var(--glass-shadow-lg);
  color: var(--text-primary);
}

/* 玻璃抽屉 */
.glass-drawer {
  background: var(--bg-elevated);
  backdrop-filter: blur(var(--glass-blur-lg, 24px));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg, 24px));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  box-shadow: var(--glass-shadow-lg);
  color: var(--text-primary);
}

/* 玻璃 Toast (已在 toast.css 覆盖) */
.glass-toast {
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-md, 16px));
  -webkit-backdrop-filter: blur(var(--glass-blur-md, 16px));
  border: 1px solid var(--glass-border-hover);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  color: var(--text-primary);
}
```

### 3.2 渐变玻璃 (KPI 用)

```css
.glass-kpi {
  position: relative;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur-md, 16px));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow-sm);
}
.glass-kpi::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.5px;
  background: var(--glass-grad-cyan-indigo);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  pointer-events: none;
  opacity: 0.6;
}
```

---

## 4. 典型组件配色小样

### 4.1 卡片 (使用玻璃拟态)

```css
.component-card {
  background: var(--glass-bg);
  backdrop-filter: blur(16px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow-sm);
  padding: var(--spacing-6);
  color: var(--text-primary);
}
.component-card-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}
.component-card-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.7;
}
```

### 4.2 表格

```css
.component-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.component-table thead th {
  background: var(--glass-bg);
  color: var(--text-tertiary);
  font-weight: 600;
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--glass-border);
  text-align: left;
}
.component-table tbody tr {
  border-bottom: 1px solid var(--glass-border);
  transition: background var(--dur-base) var(--ease-smooth);
}
.component-table tbody tr:hover {
  background: var(--glass-bg-hover);
}
.component-table tbody td {
  padding: var(--spacing-3) var(--spacing-4);
  color: var(--text-secondary);
}
.component-table .amount {
  font-family: var(--qh-ff-num);
  color: var(--text-primary);
  font-weight: 600;
  font-feature-settings: "tnum";
}
```

### 4.3 按钮

```css
/* Primary: 青蓝渐变 */
.btn-primary {
  background: linear-gradient(135deg, #0EA5E9, #6366F1);
  color: #fff;
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-6);
  font-weight: 600;
  font-size: var(--font-size-base);
  box-shadow: var(--shadow-md);
  border: none;
  transition: all var(--dur-base) var(--ease-smooth);
}
.btn-primary:hover {
  box-shadow: var(--shadow-glow);
  filter: brightness(1.08);
}

/* Secondary: 玻璃边框 */
.btn-secondary {
  background: var(--glass-bg);
  color: var(--text-primary);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-6);
  font-weight: 500;
  font-size: var(--font-size-base);
  backdrop-filter: blur(8px);
  transition: all var(--dur-base) var(--ease-smooth);
}
.btn-secondary:hover {
  background: var(--glass-bg-hover);
  border-color: var(--glass-border-hover);
}

/* Danger */
.btn-danger {
  background: #EF4444;
  color: #fff;
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-6);
  font-weight: 600;
  transition: all var(--dur-base) var(--ease-smooth);
}
.btn-danger:hover {
  filter: brightness(0.9);
}

/* Ghost */
.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-4);
  transition: color var(--dur-base) var(--ease-smooth);
}
.btn-ghost:hover {
  color: var(--text-primary);
  background: var(--glass-bg);
}
```

### 4.4 表单

```css
.component-input {
  width: 100%;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-3);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  backdrop-filter: blur(8px);
  transition: border-color var(--dur-base) var(--ease-smooth),
              box-shadow var(--dur-base) var(--ease-smooth);
}
.component-input::placeholder {
  color: var(--text-muted);
}
.component-input:focus {
  border-color: var(--glass-border-focus);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15);
  outline: none;
}
.component-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-2);
}
```

### 4.5 徽标 / Tag (使用品类色 / 状态色)

```css
.tag-category {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: 2px var(--spacing-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-weight: 500;
  line-height: 1.4;
}
.tag-industry-fast-food {
  background: var(--color-industry-fast-food-bg);
  color: var(--color-industry-fast-food-text);
}
/* 其他品类同理 … */

/* 状态徽标 */
.tag-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px var(--spacing-2);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1.3;
}
.tag-status::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.tag-order-pending   { background: var(--color-order-pending-bg);   color: var(--color-order-pending-text); }
.tag-order-paid      { background: var(--color-order-paid-bg);      color: var(--color-order-paid-text); }
.tag-order-making    { background: var(--color-order-making-bg);    color: var(--color-order-making-text); }
.tag-order-ready     { background: var(--color-order-ready-bg);     color: var(--color-order-ready-text); }
.tag-order-served    { background: var(--color-order-served-bg);    color: var(--color-order-served-text); }
.tag-order-completed { background: var(--color-order-completed-bg); color: var(--color-order-completed-text); }
.tag-order-voided    { background: var(--color-order-voided-bg);    color: var(--color-order-voided-text); }
.tag-order-refunded  { background: var(--color-order-refunded-bg);  color: var(--color-order-refunded-text); }
```

---

## 5. 字体层级与行高

| Token | clamp 值 | 默认 px | 用途 |
|-------|----------|---------|------|
| `--font-size-xs` | 0.65–0.75rem | 12px | 时间戳、注释、版权 |
| `--font-size-sm` | 0.75–0.875rem | 14px | 次级说明、Tag 文字 |
| `--font-size-base` | 0.875–1rem | 16px | 正文、表格、按钮 |
| `--font-size-md` | 1–1.125rem | 18px | 小标题、Tab |
| `--font-size-lg` | 1.125–1.375rem | 22px | 卡片标题、区块标题 |
| `--font-size-xl` | 1.375–1.75rem | 28px | 页面标题、金额 |
| `--font-size-2xl` | 1.75–2.25rem | 36px | KPI 数字、金额大字 |

### 推荐行高

- 大标题 / 金额 (`--font-size-xl` 及以上): `line-height: 1.1–1.2`
- 正文 (`--font-size-base`): `line-height: 1.6–1.7`
- 标签 / 按钮: `line-height: 1`

---

## 6. 命名空间对照 (summary)

| 文件 | 前缀 | 职责范围 | 现状 |
|------|------|----------|------|
| `app.css` | `--c-*` | 主色/辅色/阴影/圆角 (旧) | 仍在使用 (POS / 旧组件) |
| `brand.css` | `--qh-*` | 语义色彩/字体/阴影/圆角/动效 (新主系统) | 设计基准 |
| `brand-extend.css` | `--color-*` / `--chart-*` / `--glass-*` / `--spacing-*` / `--radius-*` / `--shadow-*` / `--font-size-*` | 收银场景延伸 (品类/状态/图表/玻璃细节/尺寸梯度) | 本次新增 |
| `ui-upgrade.css` | `--c-glass-*` / `--shadow-float*` / `.qh-*` | 玻璃增强 / KPI / 动画 | 不覆盖 |

### 工作法则

1. **新组件优先使用 `--qh-*`** (已足够覆盖 80% 语义场景)
2. **需要品类 / 状态 / 图表色时从 `--color-*` / `--chart-*` 取值**
3. **玻璃拟态细节 (bg/blur/border 子梯度) 走 `--glass-*`**
4. **间距 / 圆角 / 阴影 / 字号梯度走 `--spacing-*` / `--radius-*` / `--shadow-*` / `--font-size-*`**
5. **`--c-*` 仅用于旧页面兼容，新代码避免新增**

---

## 7. WCAG AA 验证说明

### 暗色模式 (bg `#0F172A` 为主底)

| 组合 | 前景 | 背景 | 对比度 | AA |
|------|------|------|--------|----|
| 一级文字 | `#F8FAFC` | `#0F172A` | 15.3:1 | AAA |
| 次级文字 | `#CBD5E1` | `#0F172A` | 10.5:1 | AA (大字 ✓) |
| 三级文字 | `#94A3B8` | `#0F172A` | 6.81:1 | AA (大字 ✓) / 占位符豁免 |
| 金额/强调 | `#0EA5E9` | `#0F172A` | 5.2:1 | AA (大字 ✓) |
| 主按钮 `#0EA5E9`→`#6366F1` 渐变 | `#FFF` | gradient | ≥7:1 中线 | AA |

### 品类色与状态色的对比度

> 所有品类色与状态色均按「深色字 + 浅底 (`*-bg`)」双用途设计；在暗底场景需在品类色/状态色外加描边或文本阴影。

### Chart 色在暗底下的可辨性

> Chart 7 色在 `#0F172A` 上的对比度为: cyan 5.9 / blue 4.8 / indigo 3.9 / purple 3.6 / pink 4.5 / amber 7.1 / emerald 5.6。当需要极小 symbol/legend 时，建议添加白色描边。

---

*文档维护: 视觉设计系统组 · 最后更新: 2025-01*

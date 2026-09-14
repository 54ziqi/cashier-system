# 设计令牌合并 — 迁移检查清单

> 接入 `tokens-merged.css` 后，以下文件中的旧令牌引用 **通过别名自动生效**，无需立即修改。
> 但建议在 3 个迭代周期内逐步替换为 `--qh-*` 权威命名。清理完成后可删除别名区段。

---

## 优先级 P0 — 有歧义/冲突风险

### `app.css`

| 行 | 旧引用 | 替换为 | 备注 |
|----|--------|--------|------|
| 4-6 | `--c-primary` (多处) | `--qh-accent` | 含 light/dark 变体 |
| 8-12 | `--c-green` (多处) | `--qh-green` | 含 light/dark/bg/text |
| 14-17 | `--c-amber` | `--qh-warning` | 含 light/bg/text |
| 19-22 | `--c-red` | `--qh-danger` | 含 light/bg/text |
| 24-26 | `--c-blue` | `--qh-info` | 含 bg/text |
| 28-35 | `--c-bg` / `-card` / `-hover` / `-border` / `-text*` | `--qh-bg` / `--qh-surface` / `--qh-line` / `--qh-ink*` | 中性色 |
| 37-40 | `--shadow-*` | `--qh-shadow-*` | 4 级 |
| 42-45 | `--r-*` | `--qh-radius-*` | 4 级 |
| 47-54 | `--sp-*` | `--qh-space-*` | 间距 |
| 56 | `--font` | `--qh-font-sans` | 字族 |
| 274 | `linear-gradient(135deg, var(--c-primary) ...)` | `var(--qh-accent)` | 登录页背景 |
| 285 | `rgba(16,185,129,.08)` | `rgba(16,185,129,.08)` (保留) | 装饰性径向渐变 |

**风险**：`app.css` `:root` 区段(第 2-57 行)定义了 `--c-*` 原始值。接入 `tokens-merged.css` 后，其 `:root` 中的 `--c-*` 会被别名定义覆盖。**建议**：将 app.css 第 2-57 行的 `:root` 块改为引用 `--qh-*`，或直接删除让 tokens-merged.css 接管。

### `brand.css`

| 行 | 旧引用 | 替换为 | 备注 |
|----|--------|--------|------|
| 全文件 | `--qh-*` | **保持不变** | 已是权威命名，tokens-merged.css 完全覆盖 |

**风险**：`brand.css` 与 `tokens-merged.css` 无冲突。但建议直接 **删除** `brand.css` 的 link，由 `tokens-merged.css` 统一提供，避免重复定义。

### `brand-extend.css`

| 行 | 旧引用 | 替换为 | 备注 |
|----|--------|--------|------|
| 23-56 | `--color-industry-*` | `--qh-industry-*` | 6 行业色 |
| 58-96 | `--color-order-*` | `--qh-order-*` | 8 状态色 |
| 103-109 | `--chart-*` | `--qh-chart-*` | 7 色板 |
| 115-142 | `--glass-*` | `--qh-glass-*` | 玻璃拟态 |
| 146-152 | `--font-size-*` | `--qh-font-*` | 字号 |
| 157-166 | `--spacing-*` | `--qh-space-*` | 间距 |
| 171-176 | `--radius-*` | `--qh-radius-*` | 圆角 |
| 181-186 | `--shadow-*` (与 app.css 同名的冲突版本) | `--qh-shadow-*` | 玻璃版阴影较深 |
| 191-211 | `--bg-*` / `--text-*` / `--border-*` | `--qh-bg-*` / `--qh-ink-*` / `--qh-line` | 暗色主题 |

**风险**：`brand-extend.css` 第 181-186 行的 `--shadow-sm` 到 `--shadow-xl` 与 `app.css` 第 37-40 行的同名变量值不同(玻璃版更深)。接入 `tokens-merged.css` 后统一为一套阴影值，需确认 `brand.css` 原有的 `--qh-shadow-1~4` 使用不受影响。

**建议**：直接 **删除** `brand-extend.css` 的 link，由 `tokens-merged.css` 统一接管。

---

## 优先级 P1 — 大量旧令牌引用

### `pages.css`

| 引用令牌 | 出现频次 | 替换为 |
|----------|----------|--------|
| `--c-border` | ~12 处 | `--qh-line` |
| `--c-bg-card` | ~8 处 | `--qh-surface` |
| `--c-text-muted` | ~6 处 | `--qh-ink-mute` |
| `--c-text-secondary` | ~4 处 | `--qh-ink-soft` |
| `--c-primary` | ~4 处 | `--qh-accent` |
| `--c-green-dark` / `--c-green` | ~4 处 | `--qh-green-strong` / `--qh-green` |
| `--c-amber` | ~2 处 | `--qh-warning` |
| `--c-red` | ~2 处 | `--qh-danger` |
| `--sp-*` | ~20 处 | `--qh-space-*` |
| `--r-*` | ~5 处 | `--qh-radius-*` |
| `--shadow-*` | ~4 处 | `--qh-shadow-*` |

**硬编码色值**：
- 第 226 行 `rgba(15,23,42,.6)` → `var(--qh-accent)` + opacity 或保留
- 第 289 行 `var(--c-green-light)` → `--qh-green-light`
- 第 474 行 `rgba(0,0,0,0.5)` → `var(--qh-glass-overlay)`
- 第 524 行 `#F0FDF4` → `var(--qh-success-bg)`

### `m1-tables.css`

| 引用令牌 | 出现频次 | 替换为 |
|----------|----------|--------|
| `--c-border` | ~8 处 | `--qh-line` |
| `--c-bg-card` | ~4 处 | `--qh-surface` |
| `--c-text-muted` | ~4 处 | `--qh-ink-mute` |
| `--c-text` | ~3 处 | `--qh-ink` |
| `--c-blue` | ~2 处 | `--qh-info` |
| `--c-amber` | ~1 处 | `--qh-warning` |
| `--c-red` | ~1 处 | `--qh-danger` |
| `--c-green-dark` | ~1 处 | `--qh-green-strong` |
| `--qh-dur-sm` / `--qh-ease-spring` | ~2 处 | `var(--dur-normal)` / `var(--ease-spring)` 或保持别名 |
| `--qh-shadow-3` | ~1 处 | `var(--qh-shadow-lg)` |

**硬编码色值**：
- 第 94 行 `#94A3B8` (桌台空状态) → `--qh-order-pending`
- 第 118 行 `#94A3B8` → `--qh-order-pending`
- 第 119 行 `#F59E0B` → `--qh-order-making`
- 第 120 行 `#3B82F6` → `--qh-info`
- 第 121 行 `#EF4444` → `--qh-danger`
- 第 189 行 `linear-gradient(90deg, #0EA5E9 0%, #6366F1 100%)` → 可保持(品牌渐变)
- 第 284-288 行 `#FEF3C7`/`#92400E`/`#D1FAE5`/`#065F46` 等 → `--qh-order-*` 系列

### `m1-pages.css`

| 引用令牌 | 出现频次 | 替换为 |
|----------|----------|--------|
| `--c-bg-card` | ~6 处 | `--qh-surface` |
| `--c-border` | ~5 处 | `--qh-line` |
| `--c-text-muted` | ~2 处 | `--qh-ink-mute` |
| `--c-primary` | ~1 处 | `--qh-accent` |
| `--c-text-secondary` | ~1 处 | `--qh-ink-soft` |
| `--r-lg` | ~4 处 | `--qh-radius-lg` |

### `m1-specs.css`

| 引用令牌 | 出现频次 | 替换为 |
|----------|----------|--------|
| `--c-border` | ~4 处 | `--qh-line` |
| `--c-text` | ~2 处 | `--qh-ink` |
| `--c-bg-card` | ~1 处 | `--qh-surface` |
| `--c-blue` | ~2 处 | `--qh-info` |
| `--c-blue-bg` | ~1 处 | `--qh-info-bg` |
| `--c-green` | ~2 处 | `--qh-green` |
| `--c-green-bg` | ~1 处 | `--qh-success-bg` |
| `--c-green-text` | ~1 处 | `--qh-success-text` |
| `--c-green-dark` | ~1 处 | `--qh-green-strong` |
| `--c-text-muted` | ~1 处 | `--qh-ink-mute` |
| `--c-red` | ~1 处 | `--qh-danger` |
| `--qh-dur-fast` | ~1 处 | `var(--dur-fast)` |

---

## 优先级 P2 — 少量引用或已使用 qh-*

### `notify.css`

| 引用令牌 | 出现频次 | 替换为 | 备注 |
|----------|----------|--------|------|
| `--radius-lg` | ~2 处 | `--qh-radius-lg` | notify 自有非 qh 变量 |
| `--shadow-lg` / `--shadow-md` / `--shadow-xl` | ~4 处 | `--qh-shadow-*` | 无 qh 前缀 |
| `--glass-bg-white` | ~3 处 | `--qh-surface` | 自定义玻璃白 |
| `--color-info` / `-success` / `-danger` / `-warning` | ~6 处 | `--qh-info/success/danger/warning` | 孤岛变量 |
| `--text-primary` / `-secondary` / `-tertiary` | ~5 处 | `--qh-ink` / `--qh-ink-soft` / `--qh-ink-mute` | 孤岛变量 |
| `--glass-border` | ~1 处 | `--qh-glass-border` | 孤岛变量 |
| `--glass-success` / `-danger` / `-warning` / `-info` | ~4 处 | `var(--qh-success-bg)` / ... | 孤岛变量 |
| `--dur-normal` / `--dur-fast` | ~5 处 | `var(--dur-slow)` / `var(--dur-fast)` | |
| `--ease-spring` / `--ease-standard` | ~4 处 | `var(--ease-spring)` / `var(--ease-standard)` | |
| `--qh-primary` | ~1 行(第 237 行) | `--qh-info` | 需确认原值 #0EA5E9 |

**注意**：`notify.css` 有自己独立的 `--glass-*` / `--text-*` / `--color-*` / `--radius-*` / `--shadow-*` 变量集，与 `qh-*` 系统并存但值不完全一致。**Phase 2 应统一**。

### `toast.css`

| 引用令牌 | 出现频次 | 备注 |
|----------|----------|------|
| `--qh-g3` / `--qh-g4` | ~4 处 | ✅ 已在 tokens-merged.css 别名中 |
| `--qh-r-md` | ~1 处 | ✅ |
| `--qh-shadow-3` | ~1 处 | ✅ |
| `--qh-ff` | ~1 处 | ✅ |
| `--qh-fs-body` | ~1 处 | ✅ |
| `--qh-ease-ease-out` | ~2 处 | ✅ |
| `--qh-ease-standard` | ~1 处 | ✅ |
| `--qh-success` / `--qh-danger` / `--qh-highlight` / `--qh-info` | 各 1 处 | ✅ |

**风险**：toast.css 已完全使用 `--qh-*` 命名，接入后 **零改动**。

### `motion.css`

| 引用令牌 | 出现频次 | 替换为 | 备注 |
|----------|----------|--------|------|
| `--shadow-lg` / `--glass-bg` / `--glass-bg-hover` / `--spacing-3` | 各 1 处 | `--qh-shadow-lg` / `--qh-glass-bg` / `--qh-space-3` | 末段场景类 |

**风险**：motion.css 主要定义 `--motion-*` 命名空间，仅在末尾场景类中混用了 `--shadow-lg` 等非 qh 变量。**Phase 2 末段清理**。

### `m1-receipt.css`

无令牌引用。硬编码色值均为打印样式(#000/#fff/#999等)，**无需迁移**。

### `ui-upgrade.css`

| 引用令牌 | 出现频次 | 替换为 |
|----------|----------|--------|
| `--c-glass` | ~2 处 | `--qh-glass-bg` |
| `--c-green-glass` | ~3 处 | `--qh-success-bg` |
| `--c-border-glass` | ~2 处 | `--qh-glass-border` |
| `--shadow-float` | ~2 处 | `--qh-shadow-glow` |
| `--shadow-pulse` | ~2 处 | `--qh-shadow-glow` |
| `--qh-dur-*` / `--qh-ease-*` | ~8 处 | `var(--dur-*)` / `var(--ease-*)` |
| `--c-green` | ~3 处 | `--qh-green` |
| `--c-blue` | ~1 处 | `--qh-info` |
| `--shadow-sm` | ~1 处 | `--qh-shadow-sm` |
| `--qh-r-md` / `--qh-surface` / `--qh-g*` / `--qh-shadow-*` / `--qh-success` / `--qh-danger` / `--qh-ink-*` | ~20 处 | ✅ 已是 qh-* |

**硬编码色值**：
- 第 239 行 SVG data URI 中的 `%2394A3B8` (= #94A3B8) → 可保留(装饰性插画)
- 第 184 行 `#10B981` / `#059669` → `--qh-green` / `--qh-green-strong`
- 第 461 行 `rgba(16, 185, 129, .35)` → `--qh-shadow-glow` 变体或保留

---

## HTML 文件检查

需要在 HTML 模板中检查 `<style>` 标签内是否有硬编码色值或旧令牌引用。按模块逐个 grep：

```bash
# 查找所有 HTML 中的旧令牌引用
grep -rn '\-\-c-\|var(--sp-\|var(--r-\|var(--shadow-\|var(--color-\|var(--glass-' templates/ static/

# 查找硬编码色值
grep -rn '#[0-9A-Fa-f]\{3,8\}' templates/ --include='*.html' | grep -v 'data:'
```

---

## 迁移完成判定标准

- [ ] 所有 CSS 文件不再使用 `--c-*` / `--sp-*` / `--r-*`(compat 除外)
- [ ] `notify.css` 的孤岛变量全部替换为 `--qh-*`
- [ ] `motion.css` 末段场景类令牌统一
- [ ] `ui-upgrade.css` 中的 `--c-glass*` / `--shadow-float` 等替换完成
- [ ] 无 HTML 内联 `<style>` 引用旧令牌
- [ ] tokens-merged.css 别名区段可安全删除
- [ ] 浏览器 DevTools 无 CSS 变量未定义警告

---

## 建议排期

| 迭代 | 范围 | 预估改动 |
|------|------|----------|
| Sprint N | 接入 tokens-merged.css，删除 brand.css / brand-extend.css link | 改 HTML 3 行 |
| Sprint N+1 | 清理 app.css / pages.css / m1-*.css 旧令牌引用 | ~200 处替换 |
| Sprint N+2 | 清理 notify.css / motion.css / ui-upgrade.css 孤岛变量 | ~50 处替换 |
| Sprint N+3 | 删除别名区段，tokens-merged.css 瘦身至 ~150 行 | 删 150 行 |

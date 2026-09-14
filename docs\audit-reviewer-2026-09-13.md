# 柒号审计报告 — Reviewer 全面审计 (2026-09-13)

## 审计摘要

| 指标 | 值 |
|------|------|
| 审计范围 | 全栈（后端 Python/FastAPI + 前端 HTML/CSS/JS） |
| 扫描文件数 | ~120+ |
| 测试用例总数 | 190 |
| 测试通过率 | **100% (190 passed)** |
| P0 发现 | 1 |
| P1 发现 | 3 |
| P2 发现 | 5 |
| 已修复确认 | 5 个 P1 全部确认到位 |

---

## P0 发现（阻断级别 — 必须修复）

### P0-1: `_apply_coupon` 优惠券类型处理完全缺失

- **位置**: `app/application/checkout/checkout_service.py:589-607`
- **描述**: `_apply_coupon` 方法仅处理 `tpl_type == "full_reduction"` 这一种券类型，但 `CouponService.create_template` 仅允许的券类型是 `"amount"` 和 `"percentage"`。这意味着：
  1. **"amount" 类型优惠券在结账时不会应用任何折扣（无 `apply_discount` 调用）** — 用户以为用了券但实际全额支付
  2. **"percentage" 类型优惠券同样无任何折扣逻辑**
  3. 如果未来有人创建 "full_reduction" 类型券模绕过 `create_template` 校验直接存库，`svc.redeem(code, order_id=order.id, session=s)` 会因 `session=s` 参数不存在而抛出 `TypeError`
- **影响**: 优惠券结账功能形同虚设，商家发券后用户使用时无折扣但有消费记录
- **修复建议**:
  1. 重写 `_apply_coupon` 中的折扣逻辑，支持 `"amount"`（直减）和 `"percentage"`（折扣率）两种类型
  2. 移除 `session=s` 参数（`redeem()` 方法不接受此参数）
  3. 或将 `CouponService.redeem()` 改为支持外部 session 注入模式（与 `WalletService`, `PointsService` 保持一致）
- **验证**: 在 `test_checkout.py` 中增加 `test_coupon_discount_amount` 和 `test_coupon_discount_percentage`，断言 `order.final_amount` 精确匹配预期折扣后金额

---

## P1 发现（重要 — 必须修复）

### P1-1: 退款时库存归还未针对 BOM 原料（M4/M5 遗漏）

- **位置**: `app/application/checkout/checkout_service.py:446-587 (refund_order 方法)`
- **描述**: `refund_order` 恢复了商品库存（`products.stock`）和扣回了积分、返还了余额，但 **未调用 `ProductionService.restore_for_refund()` 归还 BOM 原料库存**。这意味着使用原料管理的门店退款后，原料（仓库库存 + 物料总库存）不会恢复。
- **影响**: 退款后原料账面库存低于实际物理库存，导致补货建议和成本核算偏差
- **修复建议**: 在 `refund_order` 的 SAVEPOINT 内（Step 2 和 Step 3 之间）增加 `ProductionService(merchant_id=self.merchant_id).restore_for_refund(order_id)` 调用
- **验证**: 新增 `test_refund_restores_material_stock`，断言退款后 `warehouse_stocks.qty` 和 `materials.stock` 均恢复到下单前值

### P1-2: `tpl_type` 校验缺陷 — `create_template` 与 `_apply_coupon` 类型名不一致

- **位置**: 
  - `app/application/promotion/coupon_service.py:45-46` — 校验 `("amount", "percentage")`
  - `app/application/checkout/checkout_service.py:604` — 检查 `"full_reduction"`
- **描述**: 券模板创建时允许的类型和结账时处理的类型完全不一致，形成"永远为假"的条件分支。`validate_coupon` 返回的 `type` 字段值域为 `{"amount", "percentage"}`，但 `_apply_coupan` 只匹配 `"full_reduction"`。
- **影响**: 与 P0-1 同源 — 优惠券结账无折扣
- **修复建议**: 在 `_apply_coupon` 中正确处理 `"amount"` 类型：
  ```python
  if tpl_type == "amount":
      discount = min(value, order.total_amount)
      order.apply_discount(discount)
  elif tpl_type == "percentage":
      discount = int(order.total_amount * value / 100)
      order.apply_discount(discount)
  ```
- **验证**: `test_checkout_with_coupon_discount` 断言 `order.final_amount == product["price"] - expected_discount`

### P1-3: Coupon 核销未在 checkout Session 中执行（潜在跨 Session 不一致）

- **位置**: `app/application/checkout/checkout_service.py:607`
- **描述**: `svc.redeem(code, order_id=order.id, session=s)` 试图传入 `session=s`，但 `CouponService.redeem()` 方法签名为 `redeem(self, code, str, order_id: str) -> dict`，不接受 `session` 参数。若该分支被执行会直接 `TypeError`。当前因 P0-1 的死代码条件未触发，但属定时炸弹。
- **影响**: 与 P0-1 关联的稳定性风险
- **修复建议**: 为 `CouponService.redeem()` 增加 `session: Session | None = None` 参数支持（与 `WalletService`/`PointsService` 的 ext_session 模式一致），并在 `_apply_coupon` 中使用同一 Session 执行核销
- **验证**: 集成测试覆盖：下单 + 核销 + 回滚场景，确认 SAVEPOINT 异常时券状态恢复为 unused

---

## P2 发现（建议修复）

### P2-1: `_pay_cash` 积分赚取使用裸 UPDATE 无事务边界保护

- **位置**: `app/application/checkout/checkout_service.py:300-305`
- **描述**: 积分赚取使用 `s.execute(text("UPDATE members SET points = points + :pts ..."))`，当前已在 checkout 事务的 Session 中执行，这点是正确的。但 `PointsService.earn()` 方法是独立 session 无法参与外层事务。若未来有调用方在独立上下文中调用此逻辑会有并发问题。
- **风险等级**: 低（当前使用模式正确）
- **修复建议**: 在方法文档/注释中明确"S 必须在外部事务 Session 中传入"
- **验证**: 静态检查无回归即可

### P2-2: `CouponService.expire_coupons` 加载全表到内存再逐条处理

- **位置**: `app/application/promotion/coupon_service.py:270-298`
- **描述**: 过期券处理使用 `s.query(Coupon).filter_by(status="unused").all()` 加载所有未使用券到内存，再逐条比对有效期。当券量增大时存在内存和性能风险。
- **影响**: 运营超过数万张券时可能出现 OOM
- **修复建议**: 改用批量 SQL：`UPDATE coupons SET status='expired' WHERE status='unused' AND issued_at < :cutoff`
- **验证**: 性能测试 + 逻辑一致性测试

### P2-3: `checkout Service.refund_order` 中积分回滚未写入流水

- **位置**: `app/application/checkout/checkout_service.py:532-537`
- **描述**: 退款扣回积分时执行了 `UPDATE members SET points = points - :pts` 并在 `member_points_txns` 中写入了流水记录（line 538-552），**但流水记录的 `balance_after` 字段未更新**，与 `PointsService.earn/redeem` 模式不一致。
- **影响**: 积分流水链断裂，`balance_after` 校验无法通过
- **修复建议**: 在 INSERT `member_points_txns` 后读取最新 points 写入 `balance_after`
- **验证**: 断言退款后积分流水的 `balance_after` 与当前 `members.points` 一致

### P2-4: `CouponService._issue_with_code` 唯一性检查有冗余查询

- **位置**: `app/application/promotion/coupon_service.py:115-134`
- **描述**: 先查询 `existing`（line 116-117），创建 Coupon 对象后再查询一次 `existing`（line 130-132），两次查询逻辑重复。
- **影响**: 代码可读性/性能（微小）
- **修复建议**: 保留第二次查询（并发安全），移除第一次。依赖 DB UniqueConstraint 兜底。
- **验证**: 现有发券测试覆盖即可

### P2-5: `qh-modal.js` 的 `alert` 方法中 `type` 参数未实际用于样式

- **位置**: `static/js/qh-modal.js:88-96`
- **描述**: `qhModal.alert(message, type, okText)` 接收 `type` 参数但在 `notify.confirm()` 调用中未传递，导致样式不会根据类型（success/error/warning/info）变化。
- **影响**: 视觉体验 — 错误和成功弹窗样式一致
- **修复建议**: `notify.confirm(message, { title: '', okText, type })` 传递 type 参数
- **验证**: 手动验证各类型弹窗样式

---

## 已修复确认（5 个 P1）

| # | 问题 | 修复位置 | 确认状态 |
|---|------|----------|----------|
| 1 | 钱包 CAS 双花 | `app/application/member/wallet_service.py:126-133` — 余额扣减使用 `WHERE balance >= :amt` CAS 原子更新 | ✅ 确认 |
| 2 | 券 CAS 双兑 | `app/application/promotion/coupon_service.py:163-173` — 核销使用 `WHERE status = 'unused'` CAS 原子更新 | ✅ 确认 |
| 3 | 库存 CAS 超卖 | `app/application/checkout/checkout_service.py:237-250` — 商品库存扣减使用 `WHERE stock >= :qty` CAS 原子更新 | ✅ 确认 |
| 4 | void 状态校验 | `app/api/merchant/orders.py:220-224` — `void_order` 检查状态非 voided/refunded/completed | ✅ 确认 |
| 5 | 退款积分券回滚 | `app/application/checkout/checkout_service.py:518-569` — SAVEPOINT 内扣回积分和恢复券状态 | ✅ 确认 |

---

## 测试健康度

### pytest 实际结果
```
190 passed, 47 warnings in 52.59s
```

### Coverage 估算

| 模块 | 估算覆盖 | 备注 |
|------|----------|------|
| checkout_service | ~85% | 核心场景覆盖好，coupon 分支有缺陷 |
| wallet_service | ~90% | CAS/双花/退款覆盖全 |
| coupon_service | ~75% | 发券/核销覆盖，但 checkout 集成弱 |
| points_service | ~80% | 赚取/兑换/过期覆盖 |
| inventory_service | ~70% | 出入库/调拨覆盖，refund 未测 |
| order state machine | ~80% | 流转/API 覆盖 |
| 前端 JS | 0% | 无 JS 测试 |

### 薄弱测试位

| # | 薄弱点 | 文件 | 风险 |
|---|--------|------|------|
| 1 | "amount" 类型券结账折扣断言过弱 | `tests/test_m2_m3.py:743` | `assert order.final_amount <= product["price"]` 永远成立 |
| 2 | 退款后原料库存恢复未测 | 无对应测试 | P1-1 未覆盖 |
| 3 | percentage 类型券任何场景未测 | 无对应测试 | P1-2 未覆盖 |
| 4 | 券核销并发场景 | 无对应测试 | 虽有 CAS 但缺并发测试 |
| 5 | JS 前端无自动化测试 | 全部前端代码 | 质量依赖手工 |
| 6 | 变异测试未运行 | N/A | 无法评估断言杀伤力 |

---

## 关键发现汇总（按架构层次）

### 安全性
- ✅ 所有 SQL `text()` 调用均使用参数化绑定（`:param`），无 SQL 注入风险
- ✅ Token 验证使用 HMAC-SHA256 + token_version 吊销机制（非 JWT，但设计合理）
- ✅ CORS 白名单限制 localhost
- ⚠️ Token 有效期 8 小时但无自动续期（业务上合理）

### 架构合规性
- ✅ 层级依赖方向正确: domain ← application ← api，无反向依赖
- ✅ Domain 层纯领域对象，无外部框架依赖
- ✅ API 层通过 Depends 注入，无硬编码服务定位
- ⚠️ API 层部分模块在函数内 import（延迟导入），可行但非最优

### 业务逻辑正确性
- ❌ `_apply_coupon` 类型名不匹配（P0-1）
- ⚠️ 退款未恢复原料库存（P1-1）
- ⚠️ 退款积分流水 balance_after 缺失（P2-3）
- ✅ CAS 防护（钱包/库存/券）覆盖核心路径
- ✅ 状态机转换有 `_TRANSITIONS` 字典约束

### 错误处理
- ✅ SAVEPOINT 分层回滚（退款链路）
- ✅ 全局异常处理器避免泄露堆栈
- ⚠️ 部分 Service 中 `except Exception` 过于宽泛

### 前端质量
- ✅ `notify.js` 完整替代原生 alert/confirm/prompt
- ✅ `escapeHtml` 在所有 innerHTML 插值处使用
- ⚠️ `qhModal.open` 的 body/footer 参数若为 HTML 字符串则不转义（信任调用方）
- ✅ 无未捕获的 Promise rejection（全部 `.catch` 或 try/catch）

---

## 优先级行动建议

1. **立即修复**: P0-1 + P1-2（重写 `_apply_coupon` 类型匹配逻辑）
2. **本周修复**: P1-1（退款恢复原料库存）、P1-3（redeem session 参数）
3. **下个迭代**: P2-2（批量过期）、P2-3（积分流水 balance_after）
4. **质量门禁建议**: 引入变异测试（mutmut）检查断言质量，防止 "永远为真" 断言漏网

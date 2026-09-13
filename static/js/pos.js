/**
 * POS 收银台模块
 * M1 扩展: 规格选择器 / 桌台绑定 / 状态流转 / 小票
 */
const POS = (() => {
  let products = [];
  let suspendedCart = null;
  let selectedTable = null; // { id, name, capacity }

  async function init() {
    await Product.loadProducts();
    bindEvents();
  }

  function onShow() {
    renderCart();
  }

  function bindEvents() {
    // 搜索过滤
    const search = document.getElementById('pos-search');
    if (search) {
      let scanTimer = null;
      search.addEventListener('input', () => {
        if (scanTimer) clearTimeout(scanTimer);
        const val = search.value.trim();
        if (!val) { Product.renderProductGrid(products); return; }

        if (/^\d{8}$|^\d{12,14}$/.test(val)) {
          scanTimer = setTimeout(async () => {
            if (search.value.trim() !== val) return;
            try {
              const product = await API.products.getByBarcode(val);
              if (product && product.id) {
                const full = POS.products.find(p => p.id === product.id) || product;
                addToCart(full);
                Toast.success(`已添加 ${product.name}`);
                search.value = '';
                Product.renderProductGrid(products);
              }
            } catch { Product.searchProducts(val); }
          }, 150);
        } else {
          Product.searchProducts(val);
        }
      });

      search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && search.value.trim()) {
          if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }
          const val = search.value.trim();
          if (/^\d{8}$|^\d{12,14}$/.test(val)) {
            API.products.getByBarcode(val).then(product => {
              if (product && product.id) {
                addToCart(POS.products.find(p => p.id === product.id) || product);
                Toast.success(`已添加 ${product.name}`);
              }
              search.value = '';
              Product.renderProductGrid(products);
            }).catch(() => {
              Product.searchProducts(val).then(() => {
                if (POS.products.length > 0) {
                  addToCart(POS.products[0]);
                  search.value = '';
                  Product.renderProductGrid(products);
                }
              });
            });
          } else {
            Product.searchProducts(val).then(() => {
              if (POS.products.length > 0) {
                addToCart(POS.products[0]);
                search.value = '';
                Product.renderProductGrid(products);
              }
            });
          }
        }
      });
    }

    // 扫码按钮
    const scanBtn = document.getElementById('pos-scan-btn');
    if (scanBtn) {
      scanBtn.addEventListener('click', () => BarcodeScanner.toggle());
    }

    // 结算按钮
    const checkout = document.getElementById('btn-checkout');
    if (checkout) checkout.addEventListener('click', openCheckout);
    // 挂单
    const suspend = document.getElementById('btn-suspend');
    if (suspend) suspend.addEventListener('click', suspendCartFn);
    // 取单
    const resume = document.getElementById('btn-resume');
    if (resume) resume.addEventListener('click', resumeCartFn);
    // 清空
    const clear = document.getElementById('btn-clear');
    if (clear) clear.addEventListener('click', clearCart);
    // 折扣
    const discount = document.getElementById('btn-discount');
    if (discount) discount.addEventListener('click', applyDiscount);
  }

  async function handleScan(code) {
    try {
      const product = await API.products.getByBarcode(code);
      if (product) {
        addToCart(product);
      } else {
        Toast.warning(`未找到条码: ${code}`);
      }
    } catch (e) {
      Toast.warning(`未找到条码: ${code}`);
    }
  }

  /**
   * 加入购物车 — M1 规格感知
   * 如果商品有规格组，先弹出规格选择器
   */
  async function addToCart(product) {
    // 称重商品需先获取重量 (业务流程必需 — 保留 prompt 语义，使用 qhPrompt)
    if (product.is_weighing) {
      const input = await qhPrompt(`请输入${product.name}重量（${product.unit || '斤'}）：`, '1');
      if (!input || isNaN(input) || +input <= 0) {
        Toast.warning('请输入有效重量');
        return;
      }
      const qty = +input;
      const priceYuan = product.price_yuan != null ? product.price_yuan : product.price / 100;
      App.state.cart.push({
        id: product.id + '_' + Date.now(),
        product_id: product.id,
        name: product.name,
        price: product.price,
        qty: qty,
        unit: product.unit || 'pcs',
        icon: product.icon || '📦',
        weighing: true,
        subtotal: Math.round(priceYuan * qty * 100),
        spec_text: '',
        spec_selections: [],
      });
      Toast.success(`已添加: ${product.name} ${qty}${product.unit || '斤'}`);
      renderCart();
      animateCart();
      return;
    }

    // 检查是否已有相同商品+相同规格已在购物车中（非称重 + 无规格）
    const priceYuan = product.price_yuan != null ? product.price_yuan : product.price / 100;

    // 尝试获取规格
    let specResult = null;
    try {
      const specs = await API.specs.get(product.id);
      if (specs && specs.groups && specs.groups.length > 0) {
        specResult = await SpecModal.open(product);
        if (specResult === null) return; // 用户取消
      }
    } catch (e) {
      // 没有规格，静默继续
    }

    // 查找是否已有完全相同的 item (same product_id + same spec_text)
    const specKey = specResult ? specResult.spec_text : '';
    const existing = App.state.cart.find(c =>
      c.product_id === product.id &&
      !c.weighing &&
      (c.spec_text || '') === specKey
    );

    if (existing) {
      existing.qty += 1;
      existing.subtotal = Math.round(existing.price * existing.qty);
    } else {
      const finalPrice = specResult ? specResult.final_price : product.price;
      App.state.cart.push({
        id: product.id + '_' + Date.now() + Math.random().toString(36).slice(2, 6),
        product_id: product.id,
        name: product.name,
        price: finalPrice,
        qty: 1,
        unit: product.unit || 'pcs',
        icon: product.icon || '📦',
        weighing: false,
        subtotal: finalPrice,
        spec_text: specResult ? specResult.spec_text : '',
        spec_selections: specResult ? specResult.spec_selections : [],
      });
    }

    const addMsg = specResult && specResult.spec_text
      ? `+ ${product.name} (${specResult.spec_text})`
      : `+ ${product.name}`;
    Toast.success(addMsg);
    renderCart();
    animateCart();
  }

  function updateQty(id, delta) {
    const item = App.state.cart.find(c => c.id === id);
    if (!item || item.weighing) return;
    item.qty += delta;
    if (item.qty <= 0) {
      removeItem(id);
      return;
    }
    item.subtotal = Math.round(item.price * item.qty);
    renderCart();
  }

  function removeItem(id) {
    App.state.cart = App.state.cart.filter(c => c.id !== id);
    renderCart();
  }

  function getCartTotal() {
    return App.state.cart.reduce((sum, c) => sum + c.subtotal, 0);
  }

  function getItemCount() {
    return App.state.cart.reduce((sum, c) => sum + (c.weighing ? 1 : c.qty), 0);
  }

  function renderCart() {
    const itemsContainer = document.getElementById('cart-items');
    const emptyEl = document.getElementById('cart-empty');
    if (!itemsContainer) return;

    if (App.state.cart.length === 0) {
      itemsContainer.innerHTML = '';
      if (emptyEl) emptyEl.style.display = 'flex';
      updateSummary();
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';
    itemsContainer.innerHTML = '';
    App.state.cart.forEach(c => {
      const priceYuan = (c.price / 100).toFixed(2);
      const subtotalYuan = (c.subtotal / 100).toFixed(2);
      const item = document.createElement('div');
      item.className = 'cart-item';
      item.dataset.id = c.id;

      const icon = document.createElement('span');
      icon.style.cssText = 'font-size:20px;margin-right:8px';
      icon.textContent = c.icon || '📦';

      const qtyCtrl = document.createElement('div');
      qtyCtrl.className = 'qty-ctrl';
      if (!c.weighing) {
        const btnMinus = document.createElement('button');
        btnMinus.textContent = '−';
        btnMinus.addEventListener('click', () => POS.updateQty(c.id, -1));
        const qty = document.createElement('span');
        qty.className = 'qty';
        qty.textContent = c.qty;
        const btnPlus = document.createElement('button');
        btnPlus.textContent = '+';
        btnPlus.addEventListener('click', () => POS.updateQty(c.id, 1));
        qtyCtrl.appendChild(btnMinus);
        qtyCtrl.appendChild(qty);
        qtyCtrl.appendChild(btnPlus);
      } else {
        const qty = document.createElement('span');
        qty.className = 'qty';
        qty.style.cssText = 'width:auto;font-size:13px';
        qty.textContent = c.qty + c.unit;
        qtyCtrl.appendChild(qty);
      }

      const info = document.createElement('div');
      info.className = 'info';
      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = c.name;
      const price = document.createElement('div');
      price.className = 'price';
      price.textContent = '¥' + priceYuan + '/' + c.unit;
      info.appendChild(name);
      info.appendChild(price);

      // 规格文本折行展示
      if (c.spec_text) {
        const spec = document.createElement('div');
        spec.className = 'cart-item-spec';
        spec.textContent = c.spec_text;
        info.appendChild(spec);
      }

      const subtotal = document.createElement('div');
      subtotal.className = 'subtotal';
      subtotal.textContent = '¥' + subtotalYuan;

      const remove = document.createElement('button');
      remove.className = 'remove';
      remove.textContent = '×';
      remove.addEventListener('click', () => POS.removeItem(c.id));

      item.appendChild(icon);
      item.appendChild(qtyCtrl);
      item.appendChild(info);
      item.appendChild(subtotal);
      item.appendChild(remove);
      itemsContainer.appendChild(item);
    });

    updateSummary();
  }

  function updateSummary() {
    const total = getCartTotal();
    const count = getItemCount();
    const elCount = document.getElementById('cart-count');
    const elSubtotal = document.getElementById('cart-subtotal');
    const elFinal = document.getElementById('cart-final');
    if (elCount) elCount.textContent = `${count} 件`;
    if (elSubtotal) elSubtotal.textContent = '¥' + (total / 100).toFixed(2);
    if (elFinal) elFinal.textContent = '¥' + (total / 100).toFixed(2);

    const checkoutBtn = document.getElementById('btn-checkout');
    if (checkoutBtn) checkoutBtn.disabled = App.state.cart.length === 0;
  }

  function animateCart() {
    const cartEl = document.querySelector('.pos-cart');
    if (!cartEl) return;
    cartEl.style.transition = 'background-color .15s';
    cartEl.style.backgroundColor = 'var(--c-green-bg)';
    setTimeout(() => cartEl.style.backgroundColor = '', 200);
  }

  // ==================== 桌台选择 ====================

  function selectTable(table) {
    selectedTable = table;
    const badge = document.getElementById('selected-table-badge');
    const label = document.getElementById('selected-table-label');
    if (badge && label) {
      badge.style.display = 'flex';
      label.textContent = `🪑 ${table.name} (${table.capacity}人)`;
    }
  }

  function clearTableSelection() {
    selectedTable = null;
    const badge = document.getElementById('selected-table-badge');
    if (badge) badge.style.display = 'none';
  }

  // ==================== 结算 ====================

  function openCheckout() {
    if (App.state.cart.length === 0) {
      Toast.warning('购物车为空');
      return;
    }
    const total = getCartTotal();
    const modal = document.createElement('div');
    modal.className = 'modal-overlay visible';
    modal.id = 'checkout-modal';

    const tableInfo = selectedTable ? `<div style="padding:8px 16px;background:var(--c-blue-bg);color:var(--c-blue-text);font-size:13px;border-radius:8px;margin-bottom:16px;">🪑 桌台: ${escapeHtml(selectedTable.name)}</div>` : '';

    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <span>💳 结算 ¥${(total / 100).toFixed(2)}</span>
          <button class="close" onclick="POS.closeCheckout()">×</button>
        </div>
        <div class="modal-body">
          ${tableInfo}
          <div class="pay-methods">
            <div class="pay-method" data-pay="cash" onclick="POS.selectPay(this)">
              <div class="icon">💵</div><div class="name">现金</div>
            </div>
            <div class="pay-method" data-pay="member_balance" onclick="POS.selectPay(this)">
              <div class="icon">👤</div><div class="name">会员余额</div>
            </div>
            <div class="pay-method" data-pay="wechat" onclick="POS.selectPay(this)">
              <div class="icon">💚</div><div class="name">微信</div>
            </div>
          </div>
          <div class="checkout-total">
            <div class="label">应收金额</div>
            <div class="amount"><span class="yen">¥</span>${(total / 100).toFixed(2)}</div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-outline" onclick="POS.closeCheckout()">取消</button>
          <button class="btn btn-green" id="btn-confirm-pay" onclick="POS.doCheckout()">确认收款</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) POS.closeCheckout();
    });
  }

  function selectPay(el) {
    document.querySelectorAll('.pay-method').forEach(m => m.classList.remove('selected'));
    el.classList.add('selected');
  }

  async function doCheckout() {
    const selected = document.querySelector('.pay-method.selected');
    if (!selected) {
      Toast.warning('请选择支付方式');
      return;
    }
    const method = selected.dataset.pay;
    const total = getCartTotal();

    // 会员余额支付 — 输入手机号 (业务流程必需 — 使用 qhPrompt)
    let memberId = '';
    if (method === 'member_balance') {
      const phone = await qhPrompt('请输入会员手机号：');
      if (!phone) return;
      try {
        const member = await API.members.searchByPhone(phone);
        if (!member) {
          Toast.error('会员不存在');
          return;
        }
        memberId = member.id;
      } catch (e) {
        Toast.error('查找会员失败');
        return;
      }
    }

    // 现金支付 — 输入实付金额 (业务流程必需 — 使用 qhPrompt)
    let cashAmount = 0;
    if (method === 'cash') {
      const input = await qhPrompt('实收金额（元）：', (total / 100).toFixed(0));
      if (!input || isNaN(input)) return;
      cashAmount = Math.round(+input * 100);
      if (cashAmount < total) {
        Toast.error('实收金额不足');
        return;
      }
    }

    // 构造 items (M1: 携带 spec_text / spec_selections)
    const items = App.state.cart.map(c => {
      const item = {
        product_id: c.product_id || c.id,
        quantity: c.qty,
        weight: c.weighing ? c.qty : 0,
        discount: 0,
      };
      if (c.spec_text) item.spec_text = c.spec_text;
      if (c.spec_selections && c.spec_selections.length > 0) {
        item.spec_selections = c.spec_selections;
      }
      return item;
    });

    try {
      const checkoutData = {
        items,
        pay_method: method,
        member_id: memberId,
        cash_amount: cashAmount,
      };

      // M1: 桌台绑定
      if (selectedTable) {
        checkoutData.table_id = selectedTable.id;
        checkoutData.table_name = selectedTable.name;
      }

      const result = await API.cashier.checkout(checkoutData);

      // 保存 item 数据用于小票（再清空购物车）
      const receiptItems = App.state.cart.map(c => ({
        name: c.name || c.product_id,
        qty: c.qty,
        price: c.price,
        subtotal: c.subtotal,
        spec_text: c.spec_text || '',
        unit: c.unit || '',
      }));

      // 清空购物车
      App.state.cart = [];
      selectedTable = null;
      clearTableSelection();
      renderCart();
      closeCheckout();

      // M1: 展示小票
      ReceiptRenderer.showModal({
        order_no: result.order_no,
        order_id: result.order_id,
        total: result.final_amount,
        paid: result.paid_amount,
        change: result.change,
        pay_method: method,
        items: receiptItems,
        table_name: checkoutData.table_name || '',
      });

      // 结账成功 — confetti + checkmark 动效
      showCheckoutSuccess(result.order_no, method, result.change_yuan);

      // 如果是快餐且有 ready 状态 → 轮询
      pollUntilReady(result.order_id, result.order_no);

    } catch (e) {
      Toast.error('结算失败：' + e.message);
    }
  }

  /**
   * M1: 结账成功动效 — confetti + checkmark
   */
  function showCheckoutSuccess(orderNo, method, changeYuan) {
    const overlay = document.createElement('div');
    overlay.className = 'qh-checkmark-overlay';

    // Confetti 粒子
    const colors = ['#10B981', '#0EA5E9', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];
    let confettiHtml = '';
    for (let i = 0; i < 20; i++) {
      const left = Math.random() * 100;
      const color = colors[i % colors.length];
      const delay = i;
      const size = 6 + Math.random() * 6;
      const rotation = Math.random() * 360;
      confettiHtml += `<div class="qh-confetti-piece" style="left:${left}%;top:${30 + Math.random() * 20}%;--confetti-index:${delay};background:${color};width:${size}px;height:${size}px;transform:rotate(${rotation}deg)"></div>`;
    }

    const msg = method === 'cash' && changeYuan > 0
      ? `收款成功，找零 ¥${changeYuan}`
      : '收款成功';

    overlay.innerHTML = `
      ${confettiHtml}
      <div class="qh-checkmark-circle">
        <svg class="qh-checkmark-svg" viewBox="0 0 44 44"><polyline points="12,22 20,30 32,14"></polyline></svg>
      </div>
      <div class="qh-checkmark-text">${msg}</div>
    `;
    document.body.appendChild(overlay);
    setTimeout(() => overlay.remove(), 2200);
  }

  /**
   * M1: 轮询订单直到 kitchen_status=ready
   */
  function pollUntilReady(orderId, orderNo) {
    let attempts = 0;
    const maxAttempts = 60;

    const timer = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(timer);
        return;
      }
      try {
        const order = await API.get('/api/v1/merchant/orders/' + orderId);
        if (order && (order.kitchen_status === 'ready' || order.status === 'ready')) {
          clearInterval(timer);
          const qNo = order.queue_no || ('A' + orderNo.slice(-2));
          showPickupBanner(qNo);
        }
      } catch (e) {
        // 静默失败，继续轮询
      }
    }, 5000);
  }

  /**
   * M1: 顶部取餐号 banner
   */
  function showPickupBanner(number) {
    const banner = document.getElementById('pickup-banner');
    const numEl = document.getElementById('pickup-number');
    if (banner && numEl) {
      numEl.textContent = number;
      banner.style.display = 'flex';
    }
  }

  function closeCheckout() {
    const modal = document.getElementById('checkout-modal');
    if (modal) {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 200);
    }
  }

  // ==================== 挂单 / 取单 / 清空 / 折扣 ====================

  function suspendCartFn() {
    if (App.state.cart.length === 0) {
      Toast.warning('购物车为空');
      return;
    }
    suspendedCart = JSON.parse(JSON.stringify(App.state.cart));
    App.state.cart = [];
    renderCart();
    Toast.info(`已挂单 (${suspendedCart.length} 件商品)`);
  }

  async function resumeCartFn() {
    if (!suspendedCart) {
      Toast.warning('暂无挂单');
      return;
    }
    if (App.state.cart.length > 0) {
      // ::code-comment{file:"js/pos.js", title:"修复 confirm 滥用 → qhConfirm", priority:0}
      const ok = await qhConfirm('当前购物车有商品，是否覆盖恢复挂单？');
      if (!ok) return;
    }
    App.state.cart = JSON.parse(JSON.stringify(suspendedCart));
    suspendedCart = null;
    renderCart();
    Toast.success('挂单已恢复');
  }

  async function clearCart() {
    if (App.state.cart.length === 0) return;
    // ::code-comment{file:"js/pos.js", title:"修复 confirm 滥用 → qhConfirm", priority:0}
    const ok = await qhConfirm('确定清空购物车？');
    if (!ok) return;
    App.state.cart = [];
    renderCart();
    Toast.info('购物车已清空');
  }

  async function applyDiscount() {
    if (App.state.cart.length === 0) {
      Toast.warning('购物车为空');
      return;
    }
    // ::code-comment{file:"js/pos.js", title:"修复 prompt 滥用 → qhPrompt", priority:0}
    const input = await qhPrompt('请输入折扣比例（0-100，如 10 表示 9 折）：', '0');
    if (input === null) return;
    const ratio = parseFloat(input);
    if (isNaN(ratio) || ratio < 0 || ratio >= 100) {
      Toast.error('无效折扣比例');
      return;
    }
    const item = App.state.cart[App.state.cart.length - 1];
    item.subtotal = Math.round(item.price * item.qty * (1 - ratio / 100));
    renderCart();
    Toast.success(`已应用 ${ratio}% 折扣到「${item.name}」`);
  }

  return {
    init, onShow, updateQty, removeItem,
    openCheckout, closeCheckout, selectPay, doCheckout,
    suspendCart: suspendCartFn, resumeCart: resumeCartFn,
    addToCart, clearTableSelection,
    selectTable,
  };
})();

// Products 引用
Object.defineProperty(POS, 'products', {
  get: function () { return products; },
  set: function (val) { products = val; },
});

window.POS = POS;

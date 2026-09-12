/**
 * POS 收银台模块
 */
const POS = (() => {
  let products = [];
  let suspendedCart = null;

  async function init() {
    await Product.loadProducts();
    bindEvents();
  }

  function onShow() {
    renderCart();
  }

  function bindEvents() {
    // 搜索过滤（输入条码直接查询商品并添加到购物车）
    const search = document.getElementById('pos-search');
    if (search) {
      let scanTimer = null;
      search.addEventListener('input', () => {
        if (scanTimer) clearTimeout(scanTimer);
        const val = search.value.trim();
        if (!val) { Product.renderProductGrid(products); return; }

        // EAN/UPC 条码标准长度：8 (EAN-8)、12 (UPC-A)、13 (EAN-13)、14 (GTIN-14)
        if (/^\d{8}$|^\d{12,14}$/.test(val)) {
          scanTimer = setTimeout(async () => {
            if (search.value.trim() !== val) return; // 竞态保护：期间输入已变
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
          // 条码优先
          if (/^\d{8}$|^\d{12,14}$/.test(val)) {
            API.products.getByBarcode(val).then(product => {
              if (product && product.id) {
                addToCart(POS.products.find(p => p.id === product.id) || product);
                Toast.success(`已添加 ${product.name}`);
              }
              search.value = '';
              Product.renderProductGrid(products);
            }).catch(() => {
              // fallback: 普通搜索第一个
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

    // 扫码按钮 → 打开扫码弹窗
    const scanBtn = document.getElementById('pos-scan-btn');
    if (scanBtn) {
      scanBtn.addEventListener('click', () => BarcodeScanner.toggle());
    }

    // 结算按钮
    const checkout = document.getElementById('btn-checkout');
    if (checkout) checkout.addEventListener('click', openCheckout);
    // 挂单
    const suspend = document.getElementById('btn-suspend');
    if (suspend) suspend.addEventListener('click', suspendCart);
    // 取单
    const resume = document.getElementById('btn-resume');
    if (resume) resume.addEventListener('click', resumeCart);
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

  function addToCart(product) {
    // 称重商品需先获取重量
    if (product.is_weighing) {
      const input = prompt(`请输入${product.name}重量（${product.unit || '斤'}）：`, '1');
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
      });
      Toast.success(`已添加: ${product.name} ${qty}${product.unit || '斤'}`);
    } else {
      const existing = App.state.cart.find(c => c.product_id === product.id && !c.weighing);
      if (existing) {
        existing.qty += 1;
        existing.subtotal = Math.round(existing.price * existing.qty);
      } else {
        App.state.cart.push({
          id: product.id,
          product_id: product.id,
          name: product.name,
          price: product.price,
          qty: 1,
          unit: product.unit || 'pcs',
          icon: product.icon || '📦',
          weighing: false,
          subtotal: product.price,
        });
      }
      Toast.success(`+ ${product.name}`);
    }
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
      name.textContent = c.name;  // 安全：纯文本
      const price = document.createElement('div');
      price.className = 'price';
      price.textContent = '¥' + priceYuan + '/' + c.unit;
      info.appendChild(name);
      info.appendChild(price);

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

  // 结算弹窗
  function openCheckout() {
    if (App.state.cart.length === 0) {
      Toast.warning('购物车为空');
      return;
    }
    const total = getCartTotal();
    const modal = document.createElement('div');
    modal.className = 'modal-overlay visible';
    modal.id = 'checkout-modal';
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <span>💳 结算 ¥${(total / 100).toFixed(2)}</span>
          <button class="close" onclick="POS.closeCheckout()">×</button>
        </div>
        <div class="modal-body">
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

    // 如果是会员余额支付需输入手机号
    let memberId = '';
    if (method === 'member_balance') {
      const phone = prompt('请输入会员手机号：');
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

    // 现金支付需要输入实付金额
    let cashAmount = 0;
    if (method === 'cash') {
      const input = prompt('实收金额（元）：', (total / 100 * 1.0).toFixed(0));
      if (!input || isNaN(input)) return;
      cashAmount = Math.round(+input * 100);
      if (cashAmount < total) {
        Toast.error('实收金额不足');
        return;
      }
    }

    const items = App.state.cart.map(c => ({
      product_id: c.product_id || c.id,
      quantity: c.qty,
      weight: c.weighting ? c.qty : 0,
      discount: 0,
    }));

    try {
      const result = await API.cashier.checkout({
        items,
        pay_method: method,
        member_id: memberId,
        cash_amount: cashAmount,
      });

      // 清空购物车
      App.state.cart = [];
      renderCart();
      closeCheckout();

      // 显示结果
      if (method === 'cash') {
        Toast.success(`订单 ${result.order_no} 收款成功，找零 ¥${result.change_yuan}`);
      } else if (method === 'member_balance') {
        Toast.success(`订单 ${result.order_no} 会员支付成功`);
        if (result.member_balance != null) {
          setTimeout(() => Toast.info(`会员余额：¥${(result.member_balance / 100).toFixed(2)}`), 1000);
        }
      }
    } catch (e) {
      Toast.error('结算失败：' + e.message);
    }
  }

  function closeCheckout() {
    const modal = document.getElementById('checkout-modal');
    if (modal) {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 200);
    }
  }

  // 挂单/取单
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

  function resumeCartFn() {
    if (!suspendedCart) {
      Toast.warning('暂无挂单');
      return;
    }
    if (App.state.cart.length > 0) {
      if (!confirm('当前购物车有商品，是否覆盖恢复挂单？')) return;
    }
    App.state.cart = JSON.parse(JSON.stringify(suspendedCart));
    suspendedCart = null;
    renderCart();
    Toast.success('挂单已恢复');
  }

  function clearCart() {
    if (App.state.cart.length === 0) return;
    if (!confirm('确定清空购物车？')) return;
    App.state.cart = [];
    renderCart();
    Toast.info('购物车已清空');
  }

  function applyDiscount() {
    if (App.state.cart.length === 0) {
      Toast.warning('购物车为空');
      return;
    }
    const input = prompt('请输入折扣比例（0-100，如 10 表示 9 折）：', '0');
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
    addToCart, products: [], // exposed for Product module
  };
})();

// Set products reference
Object.defineProperty(POS, 'products', {
  get: function() { return products; },
  set: function(val) { products = val; },
});

window.POS = POS;

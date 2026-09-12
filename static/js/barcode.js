/**
 * 扫码枪 / 条码输入模块
 * 功能：扫描条码或手动输入编号 → 查询商品 → 自动加入购物车
 */
const BarcodeScanner = (() => {
  let modal = null;
  let input = null;
  let keydownHandler = null;

  function init() {
    createModal();
    bindGlobalListener();
  }

  function createModal() {
    modal = document.createElement('div');
    modal.className = 'barcode-modal';
    modal.innerHTML = `
      <div class="barcode-dialog">
        <div class="barcode-header">
          <span>📷 扫描/输入条码</span>
          <button id="barcode-close" style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--c-text-muted)">×</button>
        </div>
        <div class="barcode-body">
          <input type="text" id="barcode-input"
            class="barcode-input"
            placeholder="请扫描条码或手动输入商品编号"
            autocomplete="off"
            autofocus>
          <div id="barcode-result" class="barcode-result">
            <div class="hint">将光标放在这里，扫描条码即可自动添加商品</div>
          </div>
        </div>
        <div class="barcode-footer">
          <button class="btn btn-outline" id="barcode-cancel">取消</button>
          <button class="btn btn-primary" id="barcode-confirm">确认添加</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // 事件
    input = modal.querySelector('#barcode-input');
    const closeBtn = modal.querySelector('#barcode-close');
    const cancelBtn = modal.querySelector('#barcode-cancel');
    const confirmBtn = modal.querySelector('#barcode-confirm');

    const close = () => hide();
    closeBtn.addEventListener('click', close);
    cancelBtn.addEventListener('click', close);
    confirmBtn.addEventListener('click', confirmAdd);

    // 输入框回车查询
    input.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        await queryBarcode(input.value.trim());
      }
    });

    // 监听扫描枪输入（扫码枪通常以回车结束）
    input.addEventListener('input', onScannerInput);
  }

  let scanBuffer = '';
  let scanTimer = null;

  function onScannerInput(e) {
    // 扫码枪高速输入特征：短时间内连续输入多个字符
    // 普通手动输入：逐个字符输入
    if (e.inputType === 'insertText' && e.data) {
      scanBuffer += e.data;
    }

    // 清除之前的定时器
    if (scanTimer) clearTimeout(scanTimer);

    // 如果输入了回车（某些浏览器扫码枪会自动附加），立即处理
    if (scanBuffer.endsWith('\r') || scanBuffer.endsWith('\n')) {
      const code = scanBuffer.replace(/[\r\n]+$/, '').trim();
      scanBuffer = '';
      if (code) {
        input.value = code;
        queryBarcode(code);
      }
      return;
    }

    // 等待 100ms，如果不再有新输入，认为是扫描完成或手动输入
    scanTimer = setTimeout(async () => {
      const value = input.value.trim();
      if (value) {
        await queryBarcode(value);
      }
      scanBuffer = '';
    }, 100);
  }

  async function queryBarcode(code) {
    if (!code) return;
    const resultEl = modal.querySelector('#barcode-result');
    resultEl.textContent = '⏳ 查询中...';

    try {
      const product = await API.products.getByBarcode(code);
      if (product && product.id) {
        resultEl.innerHTML = '';
        const found = document.createElement('div');
        found.className = 'barcode-found';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'icon';
        iconSpan.textContent = product.icon || '📦';

        const info = document.createElement('div');
        info.className = 'info';
        const nameDiv = document.createElement('div');
        nameDiv.className = 'name';
        nameDiv.textContent = product.name;
        const priceDiv = document.createElement('div');
        priceDiv.className = 'price';
        priceDiv.textContent = '¥' + product.price_yuan + ' / ' + (product.unit || 'pcs') + ' · 库存 ' + product.stock;
        info.appendChild(nameDiv);
        info.appendChild(priceDiv);

        found.appendChild(iconSpan);
        found.appendChild(info);
        resultEl.appendChild(found);

        input.dataset.foundProduct = JSON.stringify(product);
        // 非称重商品直接自动添加到购物车
        if (!product.is_weighing && product.stock > 0) {
          addToCart(product);
        }
      } else {
        resultEl.textContent = '❌ 未找到对应商品';
        input.dataset.foundProduct = '';
      }
    } catch (err) {
      resultEl.textContent = '❌ 未找到商品 (' + code + ')';
      input.dataset.foundProduct = '';
    }
  }

  function confirmAdd() {
    const json = input.dataset.foundProduct;
    if (!json) {
      Toast.warning('请先扫描或输入有效的商品编号');
      return;
    }
    try {
      const product = JSON.parse(json);
      addToCart(product);
      hide();
    } catch (err) {
      Toast.error('添加失败：' + err.message);
    }
  }

  function addToCart(product) {
    if (product.is_weighing) {
      const weight = prompt(`请输入${product.name}重量（${product.unit || '斤'}）：`, '1');
      if (!weight || isNaN(weight) || +weight <= 0) {
        Toast.warning('请输入有效重量');
        return;
      }
      const qty = +weight;
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
        if (existing.qty + 1 > product.stock) {
          Toast.error('库存不足');
          return;
        }
        existing.qty += 1;
        existing.subtotal = Math.round(existing.price * existing.qty);
      } else {
        if (product.stock < 1) {
          Toast.error('库存不足');
          return;
        }
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
    POS.renderCart();
  }

  function bindGlobalListener() {
    // 全局监听扫码枪输入：扫码枪模拟键盘输入，以回车结尾
    let globalBuf = '';
    let globalTimer = null;

    keydownHandler = (e) => {
      // 如果弹窗已打开，由弹窗自己处理
      if (modal && modal.classList.contains('open')) return;

      // 焦点在输入框/文本域/下拉框内时，不拦截用户正常输入
      const ae = document.activeElement;
      if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.tagName === 'SELECT')) {
        return;
      }

      // 扫码枪输入通常很快（每字符 < 50ms）
      if (e.key === 'Enter' && globalBuf.length >= 4) {
        e.preventDefault();
        open(globalBuf);
        globalBuf = '';
      } else if (e.key.length === 1) {
        globalBuf += e.key;
        if (globalTimer) clearTimeout(globalTimer);
        globalTimer = setTimeout(() => { globalBuf = ''; }, 200);
      }
    };

    document.addEventListener('keydown', keydownHandler);
  }

  function open(prefill = '') {
    if (!modal) init();
    modal.classList.add('open');
    input.value = prefill;
    input.dataset.foundProduct = '';
    const result = modal.querySelector('#barcode-result');
    result.innerHTML = '<div class="hint">将光标放在这里，扫描条码即可自动添加商品</div>';
    setTimeout(() => input.focus(), 50);
  }

  function hide() {
    if (modal) modal.classList.remove('open');
    if (input) input.value = '';
  }

  function toggle() {
    if (modal && modal.classList.contains('open')) {
      hide();
    } else {
      open();
    }
  }

  return { init, open, hide, toggle, addToCart };
})();

window.BarcodeScanner = BarcodeScanner;

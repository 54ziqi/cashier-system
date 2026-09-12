/**
 * 商品管理模块
 */
const Product = (() => {

  function renderProductGrid(products) {
    const grid = document.getElementById('product-grid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!products || products.length === 0) {
      const empty = document.createElement('div');
      empty.style.cssText = 'grid-column:1/-1;text-align:center;color:var(--c-text-muted);padding:40px';
      empty.textContent = '暂无商品，请先在后台添加';
      grid.appendChild(empty);
      return;
    }
    products.forEach(p => {
      const priceYuan = (p.price_yuan != null ? p.price_yuan : p.price / 100).toFixed(2);
      const card = document.createElement('div');
      card.className = 'product-card';
      card.dataset.id = p.id;
      card.title = p.name + (p.is_weighing ? ' (称重)' : '');

      const icon = document.createElement('div');
      icon.className = 'icon';
      icon.textContent = p.icon || '📦';

      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = p.name;

      const price = document.createElement('div');
      price.className = 'price';
      price.textContent = '¥' + priceYuan + '/';
      const unitSpan = document.createElement('span');
      unitSpan.style.cssText = 'font-size:11px;font-weight:400';
      unitSpan.textContent = p.unit || 'pcs';
      price.appendChild(unitSpan);

      card.appendChild(icon);
      card.appendChild(name);
      card.appendChild(price);

      if (p.stock < 10) {
        const stock = document.createElement('div');
        stock.className = 'stock-left';
        stock.textContent = '仅剩' + p.stock + (p.unit || '件');
        card.appendChild(stock);
      }

      grid.appendChild(card);
    });

    grid.querySelectorAll('.product-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = card.dataset.id;
        const product = POS.products.find(p => p.id === id);
        if (product) POS.addToCart(product);
      });
    });
  }

  async function loadProducts() {
    try {
      const resp = await API.products.list();
      POS.products = resp.items || [];
      renderProductGrid(POS.products);
    } catch (e) {
      Toast.error('商品加载失败：' + e.message);
    }
  }

  async function searchProducts(q) {
    if (!q) return loadProducts();
    try {
      const resp = await API.products.search(q);
      renderProductGrid(resp || []);
    } catch (e) {
      Toast.error('搜索失败：' + e.message);
    }
  }

  return { loadProducts, searchProducts, renderProductGrid };
})();

window.Product = Product;

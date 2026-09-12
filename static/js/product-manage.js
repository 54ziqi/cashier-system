/**
 * 商品管理模块：分类管理 + 商品 CRUD + 搜索/筛选/上下架
 */
const ProductManage = (() => {
  let currentPage = 1;
  let currentCategory = '';
  let currentSearch = '';
  let categories = [];
  let products = [];
  let selectedIds = new Set();

  // ── Lifecycle ─────────────────────────────────

  async function onShow() {
    await Promise.all([loadCategories(), loadProducts()]);
  }

  // ── Category Management ───────────────────────

  async function loadCategories() {
    try {
      categories = await API.categories.list();
      renderCategories();
    } catch (e) {
      Toast.error('分类加载失败：' + e.message);
    }
  }

  function renderCategories() {
    const list = document.getElementById('category-list');
    if (!list) return;
    list.innerHTML = '';

    // "全部" 选项
    const allItem = document.createElement('div');
    allItem.className = 'cat-item' + (currentCategory === '' ? ' active' : '');
    allItem.dataset.cat = '';
    const allSpan = document.createElement('span');
    allSpan.textContent = '📦 全部';
    allItem.appendChild(allSpan);
    allItem.addEventListener('click', () => {
      currentCategory = '';
      currentPage = 1;
      loadProducts();
      renderCategories();
    });
    list.appendChild(allItem);

    categories.forEach(c => {
      const item = document.createElement('div');
      item.className = 'cat-item' + (currentCategory === c.id ? ' active' : '');
      item.dataset.cat = c.id;

      const span = document.createElement('span');
      span.textContent = c.name;
      item.appendChild(span);

      const actions = document.createElement('div');
      actions.className = 'cat-actions';
      const editBtn = document.createElement('button');
      editBtn.textContent = '✏️';
      editBtn.title = '编辑';
      editBtn.addEventListener('click', e => { e.stopPropagation(); editCategory(c.id); });
      const delBtn = document.createElement('button');
      delBtn.textContent = '🗑️';
      delBtn.title = '删除';
      delBtn.addEventListener('click', e => { e.stopPropagation(); deleteCategory(c.id); });
      actions.appendChild(editBtn);
      actions.appendChild(delBtn);
      item.appendChild(actions);

      item.addEventListener('click', () => {
        currentCategory = c.id;
        currentPage = 1;
        loadProducts();
        renderCategories();
      });
      list.appendChild(item);
    });
  }

  function promptCategory(data = null) {
    const isEdit = !!data;
    const name = prompt(`${isEdit ? '编辑' : '新增'}分类名称：`, data?.name || '');
    if (!name || !name.trim()) return;

    if (isEdit) {
      API.categories.update(data.id, { name: name.trim() })
        .then(() => { Toast.success('分类已更新'); loadCategories(); })
        .catch(e => Toast.error('更新失败：' + e.message));
    } else {
      API.categories.create({ name: name.trim() })
        .then(() => { Toast.success('分类已创建'); loadCategories(); })
        .catch(e => Toast.error('创建失败：' + e.message));
    }
  }

  function addCategory() {
    promptCategory(null);
  }

  function editCategory(id) {
    const cat = categories.find(c => c.id === id);
    if (cat) promptCategory(cat);
  }

  async function deleteCategory(id) {
    if (!confirm('确定删除此分类？商品不会被删除。')) return;
    try {
      await API.categories.del(id);
      Toast.success('分类已删除');
      if (currentCategory === id) {
        currentCategory = '';
        loadProducts();
      }
      loadCategories();
    } catch (e) {
      Toast.error('删除失败：' + e.message);
    }
  }

  // ── Product CRUD ──────────────────────────────

  async function loadProducts() {
    try {
      const opts = { category_id: currentCategory, q: currentSearch };
      const resp = await API.products.list(currentPage, opts);
      products = resp.items || [];
      renderProductTable();
      renderPagination(resp.total || 0);
    } catch (e) {
      Toast.error('商品加载失败：' + e.message);
    }
  }

  function renderProductTable() {
    const tbody = document.getElementById('product-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    products.forEach(p => {
      const tr = document.createElement('tr');
      tr.dataset.id = p.id;

      // 复选框
      const tdCheck = document.createElement('td');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'product-check';
      cb.dataset.id = p.id;
      cb.checked = selectedIds.has(p.id);
      cb.addEventListener('change', () => toggleSelect(p.id, cb.checked));
      tdCheck.appendChild(cb);
      tr.appendChild(tdCheck);

      // 名称 + 图标
      const tdName = document.createElement('td');
      tdName.textContent = (p.icon || '📦') + ' ' + p.name;
      tr.appendChild(tdName);

      // 分类
      const tdCat = document.createElement('td');
      const catName = p.category_id
        ? (categories.find(c => c.id === p.category_id)?.name || '未分类')
        : '—';
      tdCat.textContent = catName;
      tr.appendChild(tdCat);

      // 价格
      const tdPrice = document.createElement('td');
      tdPrice.textContent = '¥' + (p.price_yuan != null ? p.price_yuan : (p.price / 100).toFixed(2));
      tr.appendChild(tdPrice);

      // 库存
      const tdStock = document.createElement('td');
      tdStock.textContent = p.stock + ' ';
      const unitSmall = document.createElement('small');
      unitSmall.style.color = 'var(--c-text-muted)';
      unitSmall.textContent = p.unit || 'pcs';
      tdStock.appendChild(unitSmall);
      tr.appendChild(tdStock);

      // 条码
      const tdBarcode = document.createElement('td');
      const code = document.createElement('code');
      code.style.fontSize = '11px';
      code.textContent = p.barcode || '—';
      tdBarcode.appendChild(code);
      tr.appendChild(tdBarcode);

      // 状态标签
      const tdStatus = document.createElement('td');
      const tag = document.createElement('span');
      tag.className = 'status-tag ' + p.status;
      tag.textContent = p.status === 'active' ? '在售' : '下架';
      tdStatus.appendChild(tag);
      tr.appendChild(tdStatus);

      // 操作按钮
      const tdActions = document.createElement('td');
      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-outline';
      editBtn.style.cssText = 'padding:2px 8px;font-size:12px';
      editBtn.textContent = '编辑';
      editBtn.addEventListener('click', () => editProduct(p.id));

      const statusBtn = document.createElement('button');
      statusBtn.className = 'btn btn-outline';
      statusBtn.style.cssText = 'padding:2px 8px;font-size:12px' + (p.status !== 'active' ? ';color:var(--c-green)' : '');
      statusBtn.textContent = p.status === 'active' ? '下架' : '上架';
      statusBtn.addEventListener('click', () => setStatus(p.id, p.status === 'active' ? 'inactive' : 'active'));

      tdActions.appendChild(editBtn);
      tdActions.appendChild(statusBtn);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });

    // 全选复选框
    const selectAll = document.getElementById('product-select-all');
    if (selectAll) {
      selectAll.checked = selectedIds.size > 0 && selectedIds.size === products.length;
      selectAll.onchange = () => {
        if (selectAll.checked) {
          products.forEach(p => selectedIds.add(p.id));
        } else {
          selectedIds.clear();
        }
        renderProductTable();
      };
    }
  }

  function toggleSelect(id, checked) {
    if (checked) selectedIds.add(id);
    else selectedIds.delete(id);
  }

  function renderPagination(total) {
    const el = document.getElementById('product-pagination');
    if (!el) return;
    const totalPages = Math.ceil(total / 20) || 1;

    let html = `<span class="page-info">共 ${total} 件商品</span>`;
    if (selectedIds.size > 0) {
      html += `<button class="btn btn-outline" style="margin-left:12px" onclick="ProductManage.batchStatus('active')">批量上架 (${selectedIds.size})</button>`;
      html += `<button class="btn btn-outline" onclick="ProductManage.batchStatus('inactive')">批量下架 (${selectedIds.size})</button>`;
    }
    html += `<div class="page-buttons">`;
    for (let i = 1; i <= Math.min(totalPages, 10); i++) {
      html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="ProductManage.goPage(${i})">${i}</button>`;
    }
    html += `</div>`;

    el.innerHTML = html;
  }

  async function setStatus(id, status) {
    try {
      await API.products.update(id, { status });
      Toast.success(status === 'active' ? '已上架' : '已下架');
      loadProducts();
    } catch (e) {
      Toast.error('操作失败：' + e.message);
    }
  }

  async function batchStatus(status) {
    if (selectedIds.size === 0) return;
    try {
      const ids = [...selectedIds];
      await Promise.all(ids.map(id => API.products.update(id, { status })));
      selectedIds.clear();
      Toast.success(`已${status === 'active' ? '上架' : '下架'} ${ids.length} 件商品`);
      loadProducts();
    } catch (e) {
      Toast.error('批量操作失败：' + e.message);
    }
  }

  function goPage(p) {
    currentPage = p;
    loadProducts();
  }

  // ── Product Modal ─────────────────────────────

  function openEditModal(product) {
    const isEdit = !!product;
    const categoriesOptions = categories.map(c =>
      `<option value="${c.id}" ${product?.category_id === c.id ? 'selected' : ''}>${c.name}</option>`
    ).join('');

    const modal = document.createElement('div');
    modal.className = 'barcode-modal open';
    modal.id = 'product-edit-modal';
    modal.innerHTML = `
      <div class="barcode-dialog" style="width:480px">
        <div class="barcode-header">
          <span>${isEdit ? '✏️ 编辑商品' : '➕ 新增商品'}</span>
          <button onclick="document.getElementById('product-edit-modal').remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--c-text-muted)">×</button>
        </div>
        <div class="barcode-body" style="display:flex;flex-direction:column;gap:12px">
          <div class="field"><label>商品名称 *</label>
            <input class="input" id="m-name" value="${product?.name || ''}"></div>
          <div style="display:flex;gap:12px">
            <div class="field" style="flex:1"><label>价格（分）*</label>
              <input class="input" id="m-price" type="number" value="${product?.price || ''}"></div>
            <div class="field" style="flex:1"><label>库存</label>
              <input class="input" id="m-stock" type="number" value="${product?.stock || 0}"></div>
          </div>
          <div style="display:flex;gap:12px">
            <div class="field" style="flex:1"><label>条码</label>
              <input class="input" id="m-barcode" placeholder="扫描或输入条码" value="${product?.barcode || ''}"></div>
            <div class="field" style="flex:1"><label>单位</label>
              <input class="input" id="m-unit" value="${product?.unit || 'pcs'}"></div>
          </div>
          <div class="field"><label>分类</label>
            <select class="input" id="m-category">
              <option value="">— 无分类 —</option>
              ${categoriesOptions}
            </select>
          </div>
          <div style="display:flex;gap:12px">
            <div class="field" style="flex:1"><label>图标</label>
              <input class="input" id="m-icon" value="${product?.icon || '📦'}"></div>
            <div class="field" style="flex:1"><label>成本价（分）</label>
              <input class="input" id="m-cost" type="number" value="${product?.cost_price || 0}"></div>
          </div>
          <div class="field"><label>
            <input type="checkbox" id="m-weighing" ${product?.is_weighing ? 'checked' : ''}> 称重商品
          </label></div>
        </div>
        <div class="barcode-footer">
          <button class="btn btn-outline" onclick="document.getElementById('product-edit-modal').remove()">取消</button>
          <button class="btn btn-primary" id="m-save">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('#m-save').addEventListener('click', async () => {
      const data = {
        name: modal.querySelector('#m-name').value.trim(),
        price: parseInt(modal.querySelector('#m-price').value) || 0,
        stock: parseFloat(modal.querySelector('#m-stock').value) || 0,
        barcode: modal.querySelector('#m-barcode').value.trim(),
        unit: modal.querySelector('#m-unit').value.trim() || 'pcs',
        category_id: modal.querySelector('#m-category').value,
        icon: modal.querySelector('#m-icon').value.trim() || '📦',
        cost_price: parseInt(modal.querySelector('#m-cost').value) || 0,
        is_weighing: modal.querySelector('#m-weighing').checked,
      };
      if (!data.name) { Toast.warning('请输入商品名称'); return; }
      if (!data.price) { Toast.warning('请输入价格'); return; }

      try {
        if (isEdit) {
          await API.products.update(product.id, data);
          Toast.success('商品已更新');
        } else {
          await API.products.create(data);
          Toast.success('商品已创建');
        }
        modal.remove();
        loadProducts();
        // 刷新 POS 商品列表
        if (Product?.loadProducts) Product.loadProducts();
      } catch (e) {
        Toast.error('保存失败：' + e.message);
      }
    });
  }

  function openAddModal() {
    openEditModal(null);
  }

  async function editProduct(id) {
    try {
      const products = await API.products.list(1, { q: '' });
      const product = (products.items || []).find(p => p.id === id);
      if (product) openEditModal(product);
      else Toast.error('商品不存在');
    } catch (e) {
      Toast.error('加载失败：' + e.message);
    }
  }

  // ── Search Binding ────────────────────────────

  function bindSearch() {
    const searchInput = document.getElementById('product-search');
    if (!searchInput || searchInput.dataset.bound) return;
    searchInput.dataset.bound = '1';

    let timer = null;
    searchInput.addEventListener('input', () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        currentSearch = searchInput.value.trim();
        currentPage = 1;
        loadProducts();
      }, 300);
    });
  }

  return {
    onShow, loadProducts, loadCategories,
    addCategory, editCategory, deleteCategory,
    openAddModal, editProduct,
    setStatus, batchStatus, goPage, toggleSelect,
    bindSearch,
  };
})();

window.ProductManage = ProductManage;

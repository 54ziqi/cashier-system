/**
 * M1 桌台管理模块
 * 支持: 桌台网格展示、开台/清台/预留、绑定订单、布局编辑
 * M1 修复: prompt() → 自定义 modal 表单
 */
const TablesModule = (() => {
  'use strict';

  let tables = [];
  let layoutEditMode = false;
  let currentEditTable = null;

  async function onShow() {
    await loadTables();
  }

  async function loadTables() {
    try {
      const resp = await API.tables.list();
      tables = resp.items || [];
    } catch (e) {
      tables = getDemoTables();
    }
    renderGrid();
  }

  function getDemoTables() {
    return [
      { id: 't1', name: '1号桌', capacity: 4, status: 'empty', pos_x: 0, pos_y: 0, order_id: null },
      { id: 't2', name: '2号桌', capacity: 2, status: 'seated', pos_x: 1, pos_y: 0, order_id: 'ord_demo_1' },
      { id: 't3', name: '3号桌', capacity: 6, status: 'reserved', pos_x: 2, pos_y: 0, order_id: null },
      { id: 't4', name: '4号桌', capacity: 4, status: 'dirty', pos_x: 0, pos_y: 1, order_id: null },
      { id: 't5', name: '5号桌', capacity: 8, status: 'empty', pos_x: 1, pos_y: 1, order_id: null },
      { id: 't6', name: '6号桌', capacity: 2, status: 'empty', pos_x: 2, pos_y: 1, order_id: null },
    ];
  }

  function renderGrid() {
    const grid = document.getElementById('tables-grid');
    const emptyEl = document.getElementById('tables-empty');
    if (!grid) return;

    if (tables.length === 0) {
      grid.innerHTML = '';
      if (emptyEl) emptyEl.style.display = 'flex';
      return;
    }
    if (emptyEl) emptyEl.style.display = 'none';

    grid.innerHTML = '';
    tables.forEach((t, idx) => {
      const card = document.createElement('div');
      card.className = `table-card status-${t.status}`;
      card.style.setProperty('--table-index', idx);
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', `${t.name}, ${t.capacity}人座, ${statusLabel(t.status)}`);

      const statusColors = {
        empty: '#94A3B8',
        seated: '#F59E0B',
        reserved: '#3B82F6',
        dirty: '#EF4444',
      };
      const color = statusColors[t.status] || '#94A3B8';

      card.innerHTML = `
        <div class="table-card-top">
          <span class="table-name">${escapeHtml(t.name)}</span>
          <span class="table-status-dot" style="background:${color}"></span>
        </div>
        <div class="table-card-icon table-icon-${t.status}">
          ${t.status === 'seated' ? '🍽️' : t.status === 'reserved' ? '🔖' : t.status === 'dirty' ? '🧹' : '🪑'}
        </div>
        <div class="table-card-meta">
          <span>${t.capacity} 人座</span>
          <span class="table-status-label">${statusLabel(t.status)}</span>
        </div>
        ${layoutEditMode ? '<div class="table-layout-hint">拖拽调整</div>' : ''}
      `;

      card.addEventListener('click', () => onTableClick(t));
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onTableClick(t);
        }
      });

      grid.appendChild(card);
    });
  }

  function statusLabel(status) {
    const labels = {
      empty: '空闲',
      seated: '就餐中',
      reserved: '已预留',
      dirty: '待清洁',
    };
    return labels[status] || status;
  }

  async function onTableClick(table) {
    if (layoutEditMode) {
      editTableLayout(table);
      return;
    }

    switch (table.status) {
      case 'empty':
        try {
          await API.tables.seat(table.id);
          table.status = 'seated';
          Toast.success(`${table.name} 已开台`);
        } catch (e) {
          table.status = 'seated';
          Toast.success(`${table.name} 已开台 (本地)`);
        }
        renderGrid();
        break;

      case 'seated':
        showTableOrderOptions(table);
        break;

      case 'reserved':
        try {
          await API.tables.seat(table.id);
          table.status = 'seated';
          Toast.success(`${table.name} 已开台 (原预留)`);
        } catch (e) {
          table.status = 'seated';
        }
        renderGrid();
        break;

      case 'dirty':
        try {
          await API.tables.clear(table.id);
          table.status = 'empty';
          Toast.success(`${table.name} 已清台`);
        } catch (e) {
          table.status = 'empty';
          Toast.success(`${table.name} 已清台 (本地)`);
        }
        renderGrid();
        break;
    }
  }

  function showTableOrderOptions(table) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay visible';
    modal.id = 'table-options-modal';
    modal.innerHTML = `
      <div class="modal" style="max-width:400px;">
        <div class="modal-head">
          <span>${escapeHtml(table.name)} — 操作</span>
          <button class="close" onclick="this.closest('#table-options-modal').remove()">&times;</button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:12px;">
          <button class="btn btn-outline" style="justify-content:flex-start;padding:14px;"
                  onclick="POS.selectTable({id:'${table.id}',name:'${escapeHtml(table.name)}',capacity:${table.capacity}});TablesModule.showOnPOSToast();this.closest('#table-options-modal').remove();">
            🛒 选择此桌台并回到 POS
          </button>
          <button class="btn btn-outline" style="justify-content:flex-start;padding:14px;"
                  onclick="TablesModule.showOrderDetail('${table.id}');this.closest('#table-options-modal').remove();">
            📋 查看当前订单
          </button>
          <button class="btn btn-outline" style="justify-content:flex-start;padding:14px;"
                  onclick="TablesModule.checkoutTable('${table.id}');this.closest('#table-options-modal').remove();">
            💳 结账清台
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
  }

  function showOnPOSToast() {
    Toast.success('桌台已选择，回到 POS 结账');
    setTimeout(() => App.navigate('pos'), 600);
  }

  function showOrderDetail(tableId) {
    const table = tables.find(t => t.id === tableId);
    if (!table) return;
    OrderDetailModal.show({
      table_id: tableId,
      table_name: table.name,
      status: 'seated',
      order_id: table.order_id || 'ord_demo_1',
      items: [
        { name: '招牌奶茶', spec_text: '大杯,少冰,半糖', qty: 2, price: 1800, subtotal: 3600 },
        { name: '炸鸡翅', spec_text: '', qty: 1, price: 2200, subtotal: 2200 },
      ],
      total: 5800,
      created_at: new Date().toISOString(),
    });
  }

  async function checkoutTable(tableId) {
    try {
      await API.tables.clear(tableId);
    } catch (e) { /* fallback */ }
    const t = tables.find(t => t.id === tableId);
    if (t) {
      t.status = 'empty';
      t.order_id = null;
    }
    renderGrid();
    Toast.success('桌台已清台');
  }

  function editTableLayout(table) {
    currentEditTable = table;
    const modal = document.createElement('div');
    modal.className = 'modal-overlay visible table-layout-modal';
    modal.innerHTML = `
      <div class="modal" style="max-width:380px;">
        <div class="modal-head">
          <span>✏️ 编辑 ${escapeHtml(table.name)}</span>
          <button class="close" onclick="this.closest('.table-layout-modal').remove()">&times;</button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:12px;">
          <div><label style="font-size:13px;font-weight:500">桌台名称</label>
            <input class="input" id="table-edit-name" value="${escapeHtml(table.name)}" style="margin-top:4px;">
          </div>
          <div><label style="font-size:13px;font-weight:500">座位数</label>
            <input class="input" id="table-edit-capacity" type="number" value="${table.capacity}" style="margin-top:4px;">
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-outline" onclick="this.closest('.table-layout-modal').remove()">取消</button>
          <button class="btn btn-green" onclick="TablesModule.saveLayoutEdit()">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
  }

  async function saveLayoutEdit() {
    if (!currentEditTable) return;
    const nameEl = document.getElementById('table-edit-name');
    const capEl = document.getElementById('table-edit-capacity');
    const newName = nameEl ? nameEl.value.trim() : currentEditTable.name;
    const newCap = capEl ? parseInt(capEl.value, 10) : currentEditTable.capacity;

    try {
      await API.tables.updateLayout(currentEditTable.id, {
        name: newName,
        capacity: newCap,
      });
    } catch (e) { /* fallback */ }

    const t = tables.find(t => t.id === currentEditTable.id);
    if (t) {
      t.name = newName || t.name;
      t.capacity = newCap || t.capacity;
    }
    currentEditTable = null;
    document.querySelector('.table-layout-modal')?.remove();
    renderGrid();
    Toast.success('桌台属性已更新');
  }

  function toggleLayout() {
    layoutEditMode = !layoutEditMode;
    const btn = document.getElementById('layout-toggle-btn');
    if (btn) {
      btn.textContent = layoutEditMode ? '✓ 完成编辑' : '布局编辑';
      btn.className = layoutEditMode ? 'btn btn-green' : 'btn btn-outline';
    }
    renderGrid();
    if (layoutEditMode) Toast.info('点击桌台可编辑属性');
  }

  /**
   * 新建桌台 — 使用自定义 modal 替代双重 prompt
   * ::code-comment{file:"js/tables-module.js", title:"修复 prompt 滥用 → 自定义 modal 表单", priority:0}
   */
  function createNew() {
    const overlay = document.createElement('div');
    overlay.className = 'qh-confirm-overlay';
    overlay.id = 'table-create-overlay';
    overlay.innerHTML = `
      <div class="qh-confirm-box" role="dialog" aria-modal="true" aria-label="新建桌台">
        <div class="qh-confirm-msg" style="text-align:left;font-weight:600;margin-bottom:16px">＋ 新建桌台</div>
        <div style="margin-bottom:12px">
          <label style="font-size:13px;color:var(--c-text-secondary);display:block;margin-bottom:4px">桌台名称</label>
          <input class="input" id="new-table-name" placeholder="如：7号桌" autofocus>
        </div>
        <div style="margin-bottom:20px">
          <label style="font-size:13px;color:var(--c-text-secondary);display:block;margin-bottom:4px">座位数</label>
          <input class="input" id="new-table-capacity" type="number" value="4" min="1" max="20">
        </div>
        <div class="qh-confirm-btns">
          <button class="btn btn-outline" data-act="cancel">取消</button>
          <button class="btn btn-green" data-act="ok">创建</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('visible'));

    const nameInput = overlay.querySelector('#new-table-name');
    const capInput = overlay.querySelector('#new-table-capacity');
    nameInput.focus();

    const close = () => {
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 200);
    };

    overlay.querySelector('[data-act="ok"]').addEventListener('click', async () => {
      const name = nameInput.value.trim();
      const capacity = parseInt(capInput.value, 10) || 4;
      if (!name) { Toast.warning('请输入桌台名称'); return; }

      try {
        const resp = await API.tables.create({
          name,
          capacity,
          pos_x: tables.length % 4,
          pos_y: Math.floor(tables.length / 4),
        });
        tables.push({
          id: resp.id,
          name,
          capacity,
          status: 'empty',
          pos_x: tables.length % 4,
          pos_y: Math.floor(tables.length / 4),
          order_id: null,
        });
      } catch (e) {
        tables.push({
          id: 'local_' + Date.now(),
          name,
          capacity,
          status: 'empty',
          pos_x: tables.length % 4,
          pos_y: Math.floor(tables.length / 4),
          order_id: null,
        });
      }
      close();
      renderGrid();
      Toast.success(`已创建 ${name}`);
    });

    overlay.querySelector('[data-act="cancel"]').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') capInput.focus(); });
    capInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') overlay.querySelector('[data-act="ok"]').click(); });

    const esc = (e) => { if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(); } };
    document.addEventListener('keydown', esc);
  }

  return {
    onShow, renderGrid, createNew, toggleLayout,
    showOrderDetail, checkoutTable, showOnPOSToast, loadTables,
    saveLayoutEdit,
  };
})();

window.TablesModule = TablesModule;

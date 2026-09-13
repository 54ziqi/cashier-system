/**
 * M1 订单详情 + 状态流转面板
 * M1 修复: prompt() → 自定义 modal 表单
 *
 * OrderDetailModal.show(orderData)
 * orderData = {
 *   order_id, order_no, table_name, status, kitchen_status,
 *   queue_no, final_amount, items, created_at, pay_method, ...
 * }
 */
const OrderDetailModal = (() => {
  'use strict';

  // 定义每个状态对应的可用流转按钮
  const TRANSITIONS = {
    completed: [
      { to: 'making', label: '开始制作', icon: '👨‍🍳', cls: 'btn-amber' },
    ],
    making: [
      { to: 'ready', label: '制作完成', icon: '✅', cls: 'btn-green' },
    ],
    ready: [
      { to: 'served', label: '已出餐', icon: '🍽️', cls: 'btn-green' },
    ],
    paid: [
      { to: 'completed', label: '确认收款', icon: '💳', cls: 'btn-green' },
    ],
  };

  function renderTransitions(currentStatus) {
    const btns = TRANSITIONS[currentStatus] || [];
    if (btns.length === 0) {
      return '<div style="color:var(--c-text-muted);font-size:13px;text-align:center;padding:12px;">当前状态不可流转</div>';
    }
    return `
      <div class="order-transitions">
        <div class="order-transitions-title">状态流转</div>
        <div class="order-transition-btns">
          ${btns
            .map(
              (b) => `
            <button class="btn ${b.cls} order-transition-btn"
                    data-transition="${b.to}"
                    onclick="OrderDetailModal.transitionOrder('${b.to}')">
              ${b.icon} ${b.label}
            </button>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }

  function show(data) {
    const existing = document.getElementById('order-detail-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay visible order-detail-overlay';
    overlay.id = 'order-detail-modal';

    const statusLabels = {
      pending: '待处理',
      paid: '已支付',
      completed: '已完成',
      making: '制作中',
      ready: '已出餐',
      served: '已送达',
      voided: '已作废',
    };

    overlay.innerHTML = `
      <div class="modal order-detail-modal" role="dialog" aria-modal="true" aria-label="订单详情">
        <div class="modal-head">
          <span>📋 订单详情 — ${data.order_no || data.order_id || ''}</span>
          <button class="close" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body order-detail-body">
          <div class="order-meta-grid">
            ${data.table_name ? `
            <div class="order-meta-item"><span class="meta-label">桌台</span><span class="meta-value">${escapeHtml(data.table_name)}</span></div>` : ''}
            <div class="order-meta-item"><span class="meta-label">状态</span><span class="meta-value status-badge status-${data.status}">${statusLabels[data.status] || data.status}</span></div>
            <div class="order-meta-item"><span class="meta-label">下单时间</span><span class="meta-value">${escapeHtml(data.created_at ? data.created_at.slice(0, 19).replace('T', ' ') : '--')}</span></div>
            ${data.queue_no ? `<div class="order-meta-item"><span class="meta-label">取餐号</span><span class="meta-value queue-no">${escapeHtml(data.queue_no)}</span></div>` : ''}
          </div>

          <div class="order-items-section">
            <div class="order-section-title">商品明细</div>
            <div class="order-items-list">
              ${(data.items || [])
                .map(
                  (it) => `
                <div class="order-item-row">
                  <span class="oi-name">${escapeHtml(it.name)}
                    ${it.spec_text ? `<span class="oi-spec">${escapeHtml(it.spec_text)}</span>` : ''}
                  </span>
                  <span class="oi-qty">×${it.qty}</span>
                  <span class="oi-subtotal">¥${((it.subtotal || it.price * it.qty || 0) / 100).toFixed(2)}</span>
                </div>
              `
                )
                .join('')}
            </div>
            <div class="order-items-total">
              <span>合计</span>
              <span>¥${((data.total || data.final_amount || 0) / 100).toFixed(2)}</span>
            </div>
          </div>

          ${renderTransitions(data.status || 'completed')}

          <div class="order-actions-row">
            <button class="btn btn-outline" onclick="OrderDetailModal.urgeOrder()" ${data.status !== 'making' ? 'disabled' : ''}>
              催菜
            </button>
            <button class="btn btn-red" onclick="OrderDetailModal.voidOrder()">
              整单作废
            </button>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-green" onclick="OrderDetailModal.close()">关闭</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('.close').addEventListener('click', () => close());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });

    currentOrderId = data.order_id || data.order_no || null;
  }

  async function transitionOrder(transition) {
    if (!currentOrderId) return;
    try {
      await API.orderOps.transition(currentOrderId, transition);
      Toast.success(`订单已流转到: ${transition}`);
      close();
    } catch (e) {
      Toast.error(`流转失败: ${e.message}`);
    }
  }

  async function urgeOrder() {
    if (!currentOrderId) return;
    try {
      await API.orderOps.urge(currentOrderId);
      Toast.success('催菜已通知后厨');
    } catch (e) {
      Toast.error('催菜失败');
    }
  }

  /**
   * 整单作废 — 使用自定义 modal 替代原生 prompt
   * ::code-comment{file:"js/order-detail.js", title:"修复 prompt 滥用 → 自定义 modal 表单", priority:0}
   */
  function voidOrder() {
    if (!currentOrderId) return;
    const overlay = document.createElement('div');
    overlay.className = 'qh-confirm-overlay';
    overlay.innerHTML = `
      <div class="qh-confirm-box" role="dialog" aria-modal="true" aria-label="整单作废">
        <div class="qh-confirm-msg" style="text-align:left;font-weight:600;margin-bottom:8px">⚠️ 整单作废</div>
        <div style="margin-bottom:20px">
          <label style="font-size:13px;color:var(--c-text-secondary);display:block;margin-bottom:4px">请输入作废原因</label>
          <textarea class="input" id="void-reason-input" rows="3" placeholder="如：顾客取消订单" style="resize:vertical"></textarea>
        </div>
        <div class="qh-confirm-btns">
          <button class="btn btn-outline" data-act="cancel">取消</button>
          <button class="btn btn-red" data-act="ok">确认作废</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('visible'));

    const textarea = overlay.querySelector('#void-reason-input');
    textarea.focus();

    const close = () => {
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 200);
    };

    overlay.querySelector('[data-act="ok"]').addEventListener('click', async () => {
      const reason = textarea.value.trim();
      close();
      try {
        await API.orderOps.void(currentOrderId, reason);
        Toast.success('订单已作废');
        closeOrderDetail();
      } catch (e) {
        Toast.error('作废失败');
      }
    });

    overlay.querySelector('[data-act="cancel"]').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    textarea.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); overlay.querySelector('[data-act="ok"]').click(); } });
    const esc = (e) => { if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(); } };
    document.addEventListener('keydown', esc);
  }

  function closeOrderDetail() {
    const modal = document.getElementById('order-detail-modal');
    if (modal) {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 200);
    }
    currentOrderId = null;
  }

  function close() {
    closeOrderDetail();
  }

  let currentOrderId = null;

  return { show, close, transitionOrder, urgeOrder, voidOrder };
})();

window.OrderDetailModal = OrderDetailModal;

/**
 * M1 小票模板渲染器
 * renderReceipt(orderData) → HTML string
 * 支持 58mm / 80mm 切换
 *
 * orderData 结构:
 * {
 *   merchant_name, order_no, queue_no, created_at,
 *   items: [{ name, spec_text, qty, unit, price, subtotal }],
 *   total, discount, pay_method, paid, change,
 *   table_name (可选), coupon_text (可选)
 * }
 */
const ReceiptRenderer = (() => {
  'use strict';

  /**
   * 渲染小票 HTML 字符串
   */
  function render(orderData) {
    const data = normalize(orderData);
    const paperWidth = data.paper_width || '80mm';

    return `
      <div class="print-receipt receipt-paper-${paperWidth}" data-paper="${paperWidth}">
        <div class="receipt-header">
          <div class="receipt-merchant">${escapeHtml(data.merchant_name)}</div>
          ${data.queue_no ? `<div class="receipt-queue">取餐号: ${escapeHtml(data.queue_no)}</div>` : ''}
        </div>

        <div class="receipt-meta">
          <div class="receipt-row">
            <span>单号</span>
            <span>${escapeHtml(data.order_no)}</span>
          </div>
          <div class="receipt-row">
            <span>时间</span>
            <span>${escapeHtml(data.created_at)}</span>
          </div>
          ${data.table_name ? `
          <div class="receipt-row">
            <span>桌台</span>
            <span>${escapeHtml(data.table_name)}</span>
          </div>` : ''}
          <div class="receipt-row">
            <span>支付方式</span>
            <span>${escapeHtml(payMethodLabel(data.pay_method))}</span>
          </div>
        </div>

        <div class="receipt-divider"></div>

        <div class="receipt-items">
          <div class="receipt-items-header">
            <span>品名</span>
            <span>单价</span>
            <span>数量</span>
            <span>小计</span>
          </div>
          ${data.items.map((item) => renderItemRow(item)).join('')}
        </div>

        <div class="receipt-divider"></div>

        <div class="receipt-summary">
          ${data.discount > 0 ? `
          <div class="receipt-row">
            <span>优惠</span>
            <span>-¥${(data.discount / 100).toFixed(2)}</span>
          </div>` : ''}
          ${data.coupon_text ? `
          <div class="receipt-row">
            <span>优惠券</span>
            <span>${escapeHtml(data.coupon_text)}</span>
          </div>` : ''}
          <div class="receipt-row receipt-total-row">
            <span>合计</span>
            <span>¥${(data.total / 100).toFixed(2)}</span>
          </div>
          <div class="receipt-row">
            <span>实付</span>
            <span>¥${(data.paid / 100).toFixed(2)}</span>
          </div>
          ${data.change > 0 ? `
          <div class="receipt-row">
            <span>找零</span>
            <span>¥${(data.change / 100).toFixed(2)}</span>
          </div>` : ''}
        </div>

        <div class="receipt-footer">
          <div>谢谢惠顾，欢迎再来！</div>
          <div class="receipt-brand">柒号收银 · QIHAO POS</div>
        </div>
      </div>
    `;
  }

  function renderItemRow(item) {
    const parts = [];
    parts.push(`<div class="receipt-item-row">`);
    parts.push(`<div class="item-name-col">`);
    parts.push(`<span class="item-name">${escapeHtml(item.name)}</span>`);
    if (item.spec_text) {
      parts.push(`<span class="item-spec">${escapeHtml(item.spec_text)}</span>`);
    }
    parts.push(`</div>`);
    parts.push(`<span class="item-price">¥${(item.price / 100).toFixed(2)}</span>`);
    parts.push(`<span class="item-qty">${item.qty}${item.unit || ''}</span>`);
    parts.push(`<span class="item-subtotal">¥${(item.subtotal / 100).toFixed(2)}</span>`);
    parts.push(`</div>`);
    return parts.join('');
  }

  function normalize(data) {
    return {
      merchant_name: data.merchant_name || '柒号餐厅',
      order_no: data.order_no || data.order_id || '--',
      queue_no: data.queue_no || '',
      created_at: formatTime(data.created_at || new Date().toISOString()),
      items: (data.items || []).map((it) => ({
        name: it.name || '商品',
        spec_text: it.spec_text || '',
        qty: it.qty || it.quantity || 1,
        unit: it.unit || '',
        price: it.price || 0,
        subtotal: it.subtotal || 0,
      })),
      total: data.total || data.final_amount || 0,
      discount: data.discount || 0,
      pay_method: data.pay_method || 'cash',
      paid: data.paid || data.total || data.final_amount || 0,
      change: data.change || 0,
      table_name: data.table_name || '',
      coupon_text: data.coupon_text || '',
      paper_width: data.paper_width || '80mm',
    };
  }

  function formatTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch {
      return iso;
    }
  }

  function payMethodLabel(method) {
    const labels = {
      cash: '现金',
      wechat: '微信支付',
      alipay: '支付宝',
      member_balance: '会员余额',
      card: '银行卡',
    };
    return labels[method] || method;
  }

  /**
   * 展示小票 modal
   */
  function showModal(orderData) {
    const html = render(orderData);
    const existing = document.getElementById('receipt-modal');
    if ( existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay visible receipt-modal-overlay';
    overlay.id = 'receipt-modal';
    overlay.innerHTML = `
      <div class="modal receipt-modal" role="dialog" aria-modal="true" aria-label="订单小票">
        <div class="modal-head">
          <span>🧾 订单 ${escapeHtml(orderData.order_no || orderData.order_id || '')}</span>
          <button class="close" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body receipt-modal-body">
          ${html}
        </div>
        <div class="modal-foot">
          <button class="btn btn-outline" onclick="this.closest('#receipt-modal').querySelector('.receipt-modal-body .print-receipt').classList.toggle('receipt-paper-58mm');this.closest('#receipt-modal').querySelector('.receipt-modal-body .print-receipt').classList.toggle('receipt-paper-80mm')">切换纸宽</button>
          <button class="btn btn-green" onclick="window.print()">打印小票</button>
          <button class="btn btn-outline" onclick="ReceiptRenderer.closeModal()">关闭</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('.close').addEventListener('click', () => closeModal());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });
  }

  function closeModal() {
    const modal = document.getElementById('receipt-modal');
    if (modal) {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 200);
    }
  }

  return { render, showModal, closeModal };
})();

window.ReceiptRenderer = ReceiptRenderer;

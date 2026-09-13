/**
 * 柒号收银 — 品牌化 Modal & 通知核心入口
 * 扩展自 qh-modal.js，全量调用 notify 组件库，完全替代原生弹窗
 *
 * window.notify — 统一消息组件
 * window.qhModal — 品牌化 Modal 弹窗
 * window.qhConfirm / qhPrompt 兼容旧调用，底层使用 notify API
 */
 (function () {
  'use strict';

  // 兼容旧调用，直接指向 notify API
  window.qhConfirm = notify.confirm;
  window.qhPrompt = notify.prompt;

  /**
   * 品牌化 Modal 对象
   * @namespace qhModal
   */
  window.qhModal = {
    /**
     * 打开自定义 Modal
     * @param {Object} options
     * @param {string} options.title - 标题
     * @param {string|HTMLElement} options.body - 内容（HTML 字符串或 DOM 元素）
     * @param {string|HTMLElement} [options.footer] - 底部按钮区域
     * @param {Function} [options.onClose] - 关闭回调
     */
    open: ({ title, body, footer, onClose }) => {
      const overlay = document.createElement('div');
      overlay.className = 'qh-modal-overlay';
      overlay.innerHTML = `
        <div class="qh-modal-box" role="dialog" aria-modal="true" aria-label="${notify.escapeHtml(title)}">
          <div class="qh-modal-title">${notify.escapeHtml(title)}</div>
          <div class="qh-modal-body"></div>
          <div class="qh-modal-footer"></div>
        </div>
      `;
      document.body.appendChild(overlay);

      // 渲染 body
      const bodyEl = overlay.querySelector('.qh-modal-body');
      if (typeof body === 'string') {
        bodyEl.innerHTML = body;
      } else {
        bodyEl.appendChild(body);
      }

      // 渲染 footer
      const footerEl = overlay.querySelector('.qh-modal-footer');
      if (footer) {
        if (typeof footer === 'string') {
          footerEl.innerHTML = footer;
        } else {
          footerEl.appendChild(footer);
        }
      }

      requestAnimationFrame(() => overlay.classList.add('visible'));

      // 关闭逻辑
      const close = () => {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
        if (typeof onClose === 'function') onClose();
      };

      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
      const esc = (e) => { if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(); } };
      document.addEventListener('keydown', esc);

      return { close, overlay };
    },

    close: (overlay) => {
      if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
      }
    },

    /**
     * 简化 Alert 弹窗（单按钮）
     * @param {string} message - 消息内容
     * @param {'info'|'success'|'warning'|'error'} [type='info'] - 类型
     * @param {string} [okText='我知道了'] - 按钮文案
     */
    alert: (message, type = 'info', okText = '我知道了') => {
      const icons = {
        success: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
        warning: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
      };
      return notify.confirm(message, { title: '', okText, type });
    },

    confirm: notify.confirm,
    prompt: notify.prompt
  };

  // 挂载 escapeHtml 到 notify 工具方法
  notify.escapeHtml = window.escapeHtml || function(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };
})();

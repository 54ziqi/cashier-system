/**
 * Toast 通知组件
 * 用法: toast.success('操作成功'), toast.error('操作失败'), toast.info('提示'), toast.warning('警告')
 */
const Toast = (() => {
  let container = null;

  function getContainer() {
    if (!container) {
      container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
      }
    }
    return container;
  }

  function show(type, message, duration = 3000) {
    const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;

    const iconEl = document.createElement('span');
    iconEl.className = 'icon';
    iconEl.textContent = icons[type] || '';

    const msgEl = document.createElement('span');
    msgEl.className = 'msg';
    msgEl.textContent = String(message);  // 安全：纯文本，防止 XSS

    const closeEl = document.createElement('span');
    closeEl.className = 'close';
    closeEl.textContent = '×';

    el.appendChild(iconEl);
    el.appendChild(msgEl);
    el.appendChild(closeEl);

    // 点击关闭
    el.addEventListener('click', () => dismiss(el));

    getContainer().appendChild(el);

    // 自动关闭 (error 需手动关闭)
    if (type !== 'error' && duration > 0) {
      const timeout = type === 'warning' ? duration + 2000 : duration;
      setTimeout(() => dismiss(el), timeout);
    }

    return el;
  }

  function dismiss(el) {
    if (!el || el.classList.contains('closing')) return;
    el.classList.add('closing');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 350);
  }

  return {
    success: (msg) => show('success', msg, 3000),
    error: (msg) => show('error', msg, 0),
    info: (msg) => show('info', msg, 4000),
    warning: (msg) => show('warning', msg, 5000),
    dismiss
  };
})();

/**
 * HTML 转义：将 & < > " ' 转换为实体，防止 XSS
 */
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

window.Toast = Toast;
window.escapeHtml = escapeHtml;

/**
 * 柒号收银 — 统一通知提示组件库 API
 * 完全替代原生 alert / confirm / prompt，零第三方依赖
 * 
 * API:
 * notify.success(msg, options?) — 成功 Toast（3s 自动关闭）
 * notify.error(msg, options?)    — 错误 Toast（常驻，需手动关闭，aria-assertive）
 * notify.warn(msg, options?)     — 警告 Toast（5s 自动关闭）
 * notify.info(msg, options?)     — 信息 Toast（4s 自动关闭）
 * notify.banner(msg, options?)   — 顶部全局 Banner 通知
 * notify.confirm(msg, options?)  — 品牌化确认弹窗，返回 Promise<boolean>
 * notify.prompt(msg, options?)   — 品牌化输入弹窗，返回 Promise<string|null>
 * notify.suggest(el, msg, options?) — 输入框下方动态建议卡（5s 自动关闭）
 *
 * @version 1.0.0
 */
const notify = (() => {
  'use strict';

  // ---------- 工具方法 ----------
  function escapeHtml(str) {
    if (str == null) return '';
    if (window.escapeHtml) return window.escapeHtml(str);
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function getContainer(type) {
    let container;
    if (type === 'banner') {
      container = document.getElementById('notify-banner-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'notify-banner-container';
        document.body.prepend(container);
      }
    } else {
      container = document.getElementById('notify-toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'notify-toast-container';
        document.body.appendChild(container);
      }
    }
    return container;
  }

  // ---------- Toast ----------
  function showToast(type, message, options = {}) {
    const {
      action = null,
      duration = 3000,
      a11y = 'polite'
    } = options;

    const icons = {
      success: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
      error: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
      warn: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
      info: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };

    const el = document.createElement('div');
    el.className = `notify notify-toast notify-${type}`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', a11y);
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = `
      <span class="notify-icon">${icons[type]}</span>
      <span class="notify-msg">${escapeHtml(message)}</span>
      ${action ? `<button class="btn btn-ghost btn-sm" data-act="action">${escapeHtml(action.label)}</button>` : ''}
      <button class="notify-close" aria-label="关闭">×</button>
    `;

    const container = getContainer();
    container.appendChild(el);

    requestAnimationFrame(() => el.classList.add('notify-in'));

    // 自动关闭计时器
    let timer = null;
    if (type !== 'error') {
      timer = setTimeout(() => dismissToast(el), type === 'warn' ? 5000 : type === 'info' ? 4000 : duration);
    }

    // 关闭按钮
    el.querySelector('.notify-close').addEventListener('click', () => dismissToast(el));

    // 动作按钮
    if (action) {
      el.querySelector('[data-act="action"]').addEventListener('click', () => {
        if (typeof action.callback === 'function') action.callback();
        dismissToast(el);
      });
    }

    return el;
  }

  function dismissToast(el) {
    if (!el || el.classList.contains('notify-out')) return;
    el.classList.remove('notify-in');
    el.classList.add('notify-out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  }

  // ---------- Banner ----------
  function showBanner(message, options = {}) {
    const { type = 'info', closable = true } = options;
    const el = document.createElement('div');
    el.className = `notify notify-banner notify-${type}`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = `
      <span class="notify-banner-msg">${escapeHtml(message)}</span>
      ${closable ? `<button class="notify-banner-close" aria-label="关闭">×</button>` : ''}
    `;

    const container = getContainer('banner');
    container.prepend(el);
    requestAnimationFrame(() => el.classList.add('notify-banner-in'));

    if (closable) {
      el.querySelector('.notify-banner-close').addEventListener('click', () => dismissBanner(el));
    }

    return el;
  }

  function dismissBanner(el) {
    if (!el || el.classList.contains('notify-banner-out')) return;
    el.classList.remove('notify-banner-in');
    el.classList.add('notify-banner-out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  }

  // ---------- Confirm ----------
  function confirm(message, options = {}) {
    return new Promise((resolve) => {
      const {
        okText = '确定',
        cancelText = '取消',
        danger = false,
        title = '请确认'
      } = options;

      const overlay = document.createElement('div');
      overlay.className = 'qh-modal-overlay';
      overlay.innerHTML = `
        <div class="qh-modal-box" role="alertdialog" aria-modal="true" aria-label="${escapeHtml(message)}">
          <div class="qh-modal-title">${escapeHtml(title)}</div>
          <div class="qh-modal-msg">${escapeHtml(message)}</div>
          <div class="qh-modal-btns">
            <button class="btn btn-outline" data-act="cancel">${escapeHtml(cancelText)}</button>
            <button class="btn ${danger ? 'btn-danger' : 'btn-green'}" data-act="ok">${escapeHtml(okText)}</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add('visible'));

      const close = (val) => {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
        resolve(val);
      };
      overlay.querySelector('[data-act="ok"]').addEventListener('click', () => close(true));
      overlay.querySelector('[data-act="cancel"]').addEventListener('click', () => close(false));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });

      const esc = (e) => { if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(false); } };
      document.addEventListener('keydown', esc);

      setTimeout(() => overlay.querySelector('[data-act="ok"]').focus(), 50);
    });
  }

  // ---------- Prompt ----------
  function prompt(message, options = {}) {
    return new Promise((resolve) => {
      const {
        placeholder = '',
        defaultValue = '',
        title = '请输入',
        okText = '确定',
        cancelText = '取消'
      } = options;

      const overlay = document.createElement('div');
      overlay.className = 'qh-modal-overlay';
      overlay.innerHTML = `
        <div class="qh-modal-box" role="alertdialog" aria-modal="true" aria-label="${escapeHtml(message)}">
          <div class="qh-modal-title">${escapeHtml(title)}</div>
          <label class="qh-modal-msg" style="display:block;margin-bottom:12px">${escapeHtml(message)}</label>
          <input class="input qh-modal-input" type="text" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(defaultValue)}" style="margin-bottom:16px">
          <div class="qh-modal-btns">
            <button class="btn btn-outline" data-act="cancel">${escapeHtml(cancelText)}</button>
            <button class="btn btn-green" data-act="ok">${escapeHtml(okText)}</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add('visible'));

      const input = overlay.querySelector('.qh-modal-input');
      input.focus();
      input.select();

      const close = (val) => {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
        resolve(val);
      };
      overlay.querySelector('[data-act="ok"]').addEventListener('click', () => close(input.value));
      overlay.querySelector('[data-act="cancel"]').addEventListener('click', () => close(null));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); close(input.value); }
        if (e.key === 'Escape') { e.preventDefault(); close(null); }
      });
      const esc = (e) => { if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(null); } };
      document.addEventListener('keydown', esc);
    });
  }

  // ---------- Suggest ----------
  function suggest(targetEl, message, options = {}) {
    const {
      action = null,
      autoHide = true,
      delay = 5000
    } = options;

    if (document.activeElement !== targetEl) return;

    const el = document.createElement('div');
    el.className = 'notify notify-suggest';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = `
      <span class="notify-suggest-msg">${escapeHtml(message)}</span>
      ${action ? `<button class="btn btn-ghost btn-sm" data-act="action">${escapeHtml(action.label || '知道了')}</button>` : ''}
      <button class="notify-close" aria-label="关闭">×</button>
    `;

    const container = targetEl.parentElement;
    container.style.position = 'relative';
    container.appendChild(el);

    requestAnimationFrame(() => el.classList.add('notify-suggest-in'));

    let timer = autoHide ? setTimeout(() => dismissSuggest(el), delay) : null;

    el.querySelector('.notify-close').addEventListener('click', () => dismissSuggest(el));

    if (action) {
      el.querySelector('[data-act="action"]').addEventListener('click', () => {
        if (typeof action.callback === 'function') action.callback();
        dismissSuggest(el);
      });
    }

    targetEl.addEventListener('blur', () => setTimeout(() => dismissSuggest(el), 500));
    targetEl.addEventListener('focus', () => {
      if (timer) { clearTimeout(timer); timer = null; }
    });

    return el;
  }

  function dismissSuggest(el) {
    if (!el || el.classList.contains('notify-suggest-out')) return;
    el.classList.remove('notify-suggest-in');
    el.classList.add('notify-suggest-out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  }

  // 公开 API
  const success = (msg, opts) => showToast('success', msg, opts);
  const error = (msg, opts) => showToast('error', msg, { ...opts, a11y: 'assertive' });
  const warn = (msg, opts) => showToast('warn', msg, opts);
  const info = (msg, opts) => showToast('info', msg, opts);
  const banner = (msg, opts) => showBanner(msg, opts);
  const cfn = (msg, opts) => confirm(msg, opts);
  const pmt = (msg, opts) => prompt(msg, opts);
  const sgt = (el, msg, opts) => suggest(el, msg, opts);

  return { success, error, warn, info, banner, confirm: cfn, prompt: pmt, suggest: sgt };
})();

window.notify = notify;

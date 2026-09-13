/**
 * 柒号收银 — 轻量模态框替代原生 confirm / prompt
 * 零依赖、Promise 化、带完整键盘可访问性
 *
 * qhConfirm(msg)              → Promise<boolean>
 * qhPrompt(msg, defaultValue) → Promise<string|null>
 */
const qhModal = (() => {
  'use strict';

  /**
   * HTML 转义（fallback：优先用 toast.js 挂载的 window.escapeHtml）
   */
  function escapeHtml(str) {
    if (str == null) return '';
    if (window.escapeHtml) return window.escapeHtml(str);
    var div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  /**
   * 确认弹窗（替代 confirm）
   * @param {string} message
   * @returns {Promise<boolean>}
   */
  function qhConfirm(message) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'qh-confirm-overlay';
      overlay.innerHTML = `
        <div class="qh-confirm-box" role="alertdialog" aria-modal="true" aria-label="${escapeHtml(message)}">
          <div class="qh-confirm-msg">${escapeHtml(message)}</div>
          <div class="qh-confirm-btns">
            <button class="btn btn-outline" data-act="cancel">取消</button>
            <button class="btn btn-green" data-act="ok">确定</button>
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

  /**
   * 输入弹窗（替代 prompt）
   * @param {string} message
   * @param {string} [defaultValue]
   * @returns {Promise<string|null>}
   */
  function qhPrompt(message, defaultValue) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'qh-confirm-overlay';
      overlay.innerHTML = `
        <div class="qh-confirm-box" role="alertdialog" aria-modal="true" aria-label="${escapeHtml(message)}">
          <label class="qh-confirm-msg" style="display:block;margin-bottom:12px">${escapeHtml(message)}</label>
          <input class="input qh-prompt-input" type="text" value="${escapeHtml(defaultValue || '')}" style="margin-bottom:16px">
          <div class="qh-confirm-btns">
            <button class="btn btn-outline" data-act="cancel">取消</button>
            <button class="btn btn-green" data-act="ok">确定</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add('visible'));

      const input = overlay.querySelector('.qh-prompt-input');
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
    });
  }

  return { qhConfirm, qhPrompt };
})();

window.qhConfirm = qhModal.qhConfirm;
window.qhPrompt  = qhModal.qhPrompt;

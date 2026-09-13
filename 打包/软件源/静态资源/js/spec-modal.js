/**
 * M1 商品规格选择器组件
 * 纯 vanilla JS，零依赖
 * 调用：SpecModal.open(product).then(result => ...)
 *   result = { spec_text, spec_selections, final_price }
 *   result = null (用户取消)
 */
const SpecModal = (() => {
  'use strict';

  /**
   * 打开规格选择弹窗
   * @param {Object} product - 商品对象 { id, name, price, icon }
   * @returns {Promise<{spec_text, spec_selections, final_price} | null>}
   */
  function open(product) {
    return new Promise((resolve) => {
      // 1. 先获取规格数据（本地优先，fallback 到 API）
      fetchSpecs(product.id)
        .then((specs) => {
          if (!specs || !specs.groups || specs.groups.length === 0) {
            // 该商品没有规格，直接返回基础价格
            resolve({
              spec_text: '',
              spec_selections: [],
              final_price: product.price,
            });
            return;
          }
          renderModal(product, specs, resolve);
        })
        .catch(() => {
          // 规格加载失败 → 走基础价格
          resolve({
            spec_text: '',
            spec_selections: [],
            final_price: product.price,
          });
        });
    });
  }

  async function fetchSpecs(productId) {
    try {
      return await API.specs.get(productId);
    } catch (e) {
      return null;
    }
  }

  function renderModal(product, specs, resolve) {
    // 已选状态：{ group_name: [option_value, ...] }
    const selections = {};
    specs.groups.forEach((g) => {
      selections[g.group_name] = [];
    });

    // 创建弹窗 DOM
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay spec-modal-overlay';
    overlay.id = 'spec-modal';

    const basePrice = product.price; // 分

    overlay.innerHTML = `
      <div class="modal spec-modal" role="dialog" aria-modal="true" aria-label="选择规格 - ${escapeHtml(product.name)}">
        <div class="modal-head">
          <span>⚙️ ${escapeHtml(product.name)} — 选择规格</span>
          <button class="close" aria-label="取消">&times;</button>
        </div>
        <div class="modal-body spec-modal-body">
          ${specs.groups.map((group) => renderGroup(group, specs.options)).join('')}
          <div class="spec-total-row">
            <span class="spec-total-label">合计</span>
            <span class="spec-total-price" id="spec-total-price">¥${(basePrice / 100).toFixed(2)}</span>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-outline spec-btn-cancel">取消</button>
          <button class="btn btn-green spec-btn-confirm" id="spec-confirm-btn">确认</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // 入场动画
    requestAnimationFrame(() => overlay.classList.add('visible'));

    // 事件绑定
    const closeBtn = overlay.querySelector('.close');
    const cancelBtn = overlay.querySelector('.spec-btn-cancel');
    const confirmBtn = overlay.querySelector('#spec-confirm-btn');

    function close(result) {
      overlay.classList.remove('visible');
      setTimeout(() => {
        overlay.remove();
        resolve(result);
      }, 200);
    }

    closeBtn.addEventListener('click', () => close(null));
    cancelBtn.addEventListener('click', () => close(null));
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(null);
    });

    // 规格选项点击
    overlay.querySelectorAll('.spec-option-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const groupName = btn.dataset.group;
        const value = btn.dataset.value;
        const groupDef = specs.groups.find((g) => g.group_name === groupName);
        if (!groupDef) return;

        const isMulti = groupDef.max_select > 1;
        const sel = selections[groupName];

        if (isMulti) {
          // checkbox 模式：多选切换
          const idx = sel.indexOf(value);
          if (idx >= 0) {
            sel.splice(idx, 1);
            btn.classList.remove('selected');
          } else {
            if (sel.length >= groupDef.max_select) {
              Toast.warning(`最多选 ${groupDef.max_select} 项`);
              return;
            }
            sel.push(value);
            btn.classList.add('selected');
          }
        } else {
          // radio 模式：单选
          sel.length = 0;
          sel.push(value);
          // 同组其他按钮取消 selected
          overlay
            .querySelectorAll(`.spec-option-btn[data-group="${CSS.escape(groupName)}"]`)
            .forEach((b) => b.classList.remove('selected'));
          btn.classList.add('selected');
        }

        updateTotal();
        updateConfirmState();
      });
    });

    // 更新总价
    function updateTotal() {
      let delta = 0;
      specs.groups.forEach((group) => {
        const selValues = selections[group.group_name];
        selValues.forEach((val) => {
          const opt = specs.options.find(
            (o) => o.option_name === group.group_name && o.value === val
          );
          if (opt) delta += opt.price_delta || 0;
        });
      });
      const total = basePrice + delta;
      const el = overlay.querySelector('#spec-total-price');
      if (el) el.textContent = '¥' + (total / 100).toFixed(2);
    }

    // 更新确认按钮状态（必选型未满足则禁用）
    function updateConfirmState() {
      let valid = true;
      specs.groups.forEach((group) => {
        if (group.required && selections[group.group_name].length < (group.min_select || 1)) {
          valid = false;
        }
      });
      confirmBtn.disabled = !valid;
    }
    updateConfirmState();

    // 确认
    confirmBtn.addEventListener('click', () => {
      // 构造结果
      const selValues = [];
      let delta = 0;
      const textParts = [];

      specs.groups.forEach((group) => {
        selections[group.group_name].forEach((val) => {
          selValues.push({ group: group.group_name, value: val });
          const opt = specs.options.find(
            (o) => o.option_name === group.group_name && o.value === val
          );
          if (opt) {
            delta += opt.price_delta || 0;
            const sign = opt.price_delta > 0 ? '+' : '';
            textParts.push(`${val}${sign}¥${(opt.price_delta / 100).toFixed(2)}`);
          } else {
            textParts.push(val);
          }
        });
      });

      close({
        spec_text: textParts.join(' / '),
        spec_selections: selValues,
        final_price: basePrice + delta,
      });
    });

    // 键盘 Esc 关闭
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        close(null);
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  /**
   * 渲染单个规格组
   */
  function renderGroup(group, options) {
    const groupOptions = options.filter((o) => o.option_name === group.group_name);
    const isMulti = group.max_select > 1;
    const requiredMark = group.required ? '<span class="spec-required">*</span>' : '';
    const multiHint = isMulti ? `<span class="spec-multi-hint">(可多选)</span>` : '';

    return `
      <div class="spec-group" data-group="${escapeHtml(group.group_name)}">
        <div class="spec-group-title">
          ${escapeHtml(group.group_name)} ${requiredMark} ${multiHint}
        </div>
        <div class="spec-options">
          ${groupOptions
            .map(
              (opt) => `
            <button class="spec-option-btn ${isMulti ? 'is-multi' : 'is-radio'}"
                    data-group="${escapeHtml(group.group_name)}"
                    data-value="${escapeHtml(opt.value)}"
                    role="${isMulti ? 'checkbox' : 'radio'}"
                    aria-checked="false">
              <span class="spec-opt-value">${escapeHtml(opt.value)}</span>
              ${
                opt.price_delta
                  ? `<span class="spec-opt-delta">${opt.price_delta > 0 ? '+' : ''}¥${(opt.price_delta / 100).toFixed(2)}</span>`
                  : ''
              }
            </button>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }

  return { open };
})();

window.SpecModal = SpecModal;

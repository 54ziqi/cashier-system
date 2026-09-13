/**
 * 会员管理模块
 */
const Member = (() => {
  async function onShow() {
    await renderMemberList();
  }

  async function renderMemberList() {
    const container = document.getElementById('member-list');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--c-text-muted)">加载中…</div>';

    try {
      const resp = await API.members.list();
      const members = resp.items || [];

      if (members.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--c-text-muted)">暂无会员</div>';
        return;
      }

      container.innerHTML = '';
      members.forEach(m => {
        const balanceYuan = ((m.balance_yuan != null ? m.balance_yuan : (m.balance || 0) / 100) || 0).toFixed(2);
        const item = document.createElement('div');
        item.className = 'cart-item';
        item.style.cursor = 'pointer';
        item.dataset.id = m.id;
        item.addEventListener('click', () => Member.selectMember(m.id));

        const icon = document.createElement('span');
        icon.style.cssText = 'font-size:24px;margin-right:12px';
        icon.textContent = m.level === 'gold' ? '👑' : m.level === 'silver' ? '⭐' : '👤';

        const info = document.createElement('div');
        info.className = 'info';
        const nameRow = document.createElement('div');
        nameRow.className = 'name';
        nameRow.textContent = m.name || '-';
        const levelSpan = document.createElement('span');
        levelSpan.style.cssText = 'font-size:11px;color:var(--c-text-muted)';
        levelSpan.textContent = ' ' + m.level;
        nameRow.appendChild(levelSpan);
        const subRow = document.createElement('div');
        subRow.style.cssText = 'font-size:12px;color:var(--c-text-muted)';
        subRow.textContent = (m.phone || '-') + ' · ' + (m.card_no || '-');
        info.appendChild(nameRow);
        info.appendChild(subRow);

        const right = document.createElement('div');
        right.style.cssText = 'text-align:right;font-size:13px';
        const balanceEl = document.createElement('div');
        balanceEl.style.cssText = 'color:var(--c-green-dark);font-weight:600';
        balanceEl.textContent = '余额 ¥' + balanceYuan;
        const pointsEl = document.createElement('div');
        pointsEl.style.cssText = 'color:var(--c-text-muted)';
        pointsEl.textContent = '积分 ' + (m.points || 0);
        right.appendChild(balanceEl);
        right.appendChild(pointsEl);

        item.appendChild(icon);
        item.appendChild(info);
        item.appendChild(right);
        container.appendChild(item);
      });
    } catch (e) {
      container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--c-red)">加载失败</div>';
    }
  }

  function selectMember(id) {
    Toast.info(`选中会员 ID: ${id}`);
  }

  return { onShow };
})();

window.Member = Member;

/**
 * 设备管理模块
 */
const HW = (() => {
  function onShow() {
    renderHWGrid();
  }

  function renderHWGrid() {
    const grid = document.getElementById('hw-grid');
    if (!grid) return;

    const hwList = [
      { key: 'scanner', name: '扫码枪', icon: '📷', connection: 'USB-HID', desc: '即插即用，支持一维/二维条码', testMsg: '触发扫码…请在扫码枪输入内容' },
      { key: 'printer', name: '小票打印机', icon: '🖨️', connection: 'USB / Serial', desc: 'ESC/POS 指令集，80mm 纸宽', testMsg: '打印测试页…' },
      { key: 'scale', name: '电子秤', icon: '⚖️', connection: 'RS232 / Serial', desc: '精度 1/3000，支持去皮', testMsg: '读取重量…' },
      { key: 'display', name: '客显/收款码屏', icon: '🖥️', connection: 'WebSocket', desc: '实时显示商品与金额', testMsg: '测试客显…' },
    ];

    grid.innerHTML = hwList.map(hw => {
      const status = App.state.hardware[hw.key]?.status || 'offline';
      const statusText = status === 'online' ? '在线' : status === 'warning' ? '警告' : '离线';
      const toggleStatus = status === 'online' ? 'offline' : 'online';
      return `
        <div class="hw-card">
          <div class="hw-head">
            <div class="hw-icon ${status}">${hw.icon}</div>
            <div class="hw-name">${hw.name}</div>
            <span class="hw-status ${status}">${statusText}</span>
          </div>
          <div class="hw-meta">
            <div>连接方式：${hw.connection}</div>
            <div>${hw.desc}</div>
          </div>
          <div class="hw-actions">
            <button class="btn btn-outline" onclick="document.dispatchEvent(new CustomEvent('hw-toggle',{detail:'${hw.key}'}))">切换状态</button>
            <button class="btn btn-primary" onclick="Toast.info('${hw.testMsg}')">测试</button>
          </div>
        </div>
      `;
    }).join('');

    // 监听切换事件
    document.querySelectorAll('.hw-card .btn-outline').forEach(btn => {
      // 已在 onclick 中处理
    });
  }

  // 供外部调用
  function toggleDevice(key) {
    const dev = App.state.hardware[key];
    if (!dev) return;
    dev.status = dev.status === 'online' ? 'offline' : 'online';
    renderHWBar2();
    onShow();
  }

  return { onShow, toggleDevice };
})();

window.HW = HW;

// 全局硬件切换
document.addEventListener('hw-toggle', (e) => {
  HW.toggleDevice(e.detail);
});

function renderHWBar2() {
  const bar = document.getElementById('hw-bar');
  if (!bar) return;
  bar.innerHTML = '';
  Object.entries(App.state.hardware).forEach(([key, dev]) => {
    const item = document.createElement('div');
    item.className = 'hw-item';
    item.innerHTML = `<span class="dot ${dev.status}"></span><span>${dev.icon}</span><span class="name">${dev.name}</span>`;
    item.addEventListener('click', () => App.navigate('hw'));
    bar.appendChild(item);
  });
}

/**
 * Cashier 收银系统 - 主应用入口
 * 路由 / 顶栏 / 硬件条 / 登录守卫
 */
(function () {
  'use strict';

  // ============ 全局状态 ============
  const state = {
    user: null,
    cart: [],           // { id, name, price, qty, icon, stock }
    products: [],       // 商品列表
    members: [],
    currentPage: 'pos',
    hardware: {
      scanner: { name: '扫码枪', status: 'offline', icon: '📷' },
      printer: { name: '小票机', status: 'offline', icon: '🖨️' },
      scale:   { name: '电子秤', status: 'offline', icon: '⚖️' },
      display: { name: '客显',   status: 'offline', icon: '🖥️' },
    }
  };

  // ============ 路由 ============
  function navigate(pageId) {
    state.currentPage = pageId;
    // 更新 tab 高亮
    document.querySelectorAll('.topbar .nav button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.page === pageId);
    });
    // 切换 page 显示
    document.querySelectorAll('.page').forEach(p => {
      p.classList.toggle('active', p.id === 'page-' + pageId);
    });
    // 页面初始化钩子
    if (pageId === 'pos') {
      POS.onShow();
      BarcodeScanner.init();
    }
    if (pageId === 'member') Member.onShow();
    if (pageId === 'report') Report.onShow();
    if (pageId === 'hw') HW.onShow();
    if (pageId === 'products') {
      ProductManage.onShow();
      ProductManage.bindSearch();
      BarcodeScanner.init();
    }
  }

  // ============ 顶栏时钟 ============
  function startClock() {
    const update = () => {
      const el = document.getElementById('topbar-time');
      if (!el) return;
      const now = new Date();
      el.textContent = now.toLocaleString('zh-CN', {
        hour12: false,
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    };
    update();
    setInterval(update, 1000);
  }

  // ============ 硬件状态条 ============
  function renderHWBar() {
    const bar = document.getElementById('hw-bar');
    if (!bar) return;
    bar.innerHTML = '';
    Object.entries(state.hardware).forEach(([key, dev]) => {
      const item = document.createElement('div');
      item.className = 'hw-item';
      item.innerHTML = `
        <span class="dot ${dev.status}"></span>
        <span>${dev.icon}</span>
        <span class="name">${dev.name}</span>
      `;
      item.addEventListener('click', () => navigate('hw'));
      bar.appendChild(item);
    });
  }

  // 模拟硬件状态随机变化（演示用）
  function simulateHW() {
    const statuses = ['online', 'online', 'online', 'offline', 'warning'];
    setInterval(() => {
      const keys = Object.keys(state.hardware);
      const key = keys[Math.floor(Math.random() * keys.length)];
      const oldStatus = state.hardware[key].status;
      const newStatus = statuses[Math.floor(Math.random() * statuses.length)];
      if (oldStatus !== newStatus) {
        state.hardware[key].status = newStatus;
        renderHWBar();
        if (newStatus === 'online') Toast.success(`${state.hardware[key].name} 已连接`);
        else if (newStatus === 'offline') Toast.warning(`${state.hardware[key].name} 已断开`);
      }
    }, 8000);
  }

  // ============ Login 登录 ============
  async function doLogin() {
    const u = document.getElementById('login-user').value.trim() || 'admin';
    const p = document.getElementById('login-pass').value;
    const btn = document.getElementById('login-btn');
    const msg = document.getElementById('login-msg');

    if (!p) {
      msg.textContent = '请输入密码';
      msg.className = 'text-red';
      return;
    }

    btn.disabled = true;
    btn.textContent = '登录中…';
    msg.textContent = '';

    try {
      const data = await API.auth.login(u, p);
      API.setToken(data.token);
      state.user = await API.auth.me();
      enterMain();
      Toast.success(`欢迎回来，${state.user.username}`);
    } catch (e) {
      if (e.status === 401) {
        msg.textContent = '用户名或密码错误';
      } else {
        msg.textContent = e.message || '登录失败';
      }
      msg.className = 'text-red';
    } finally {
      btn.disabled = false;
      btn.textContent = '登 录';
    }
  }

  // 进入主界面
  function enterMain() {
    document.getElementById('login-page').style.display = 'none';
    document.getElementById('main-app').style.display = 'flex';

    // 渲染顶栏用户
    document.getElementById('topbar-user').textContent = state.user?.username || '';
    // 硬件条
    renderHWBar();
    simulateHW();
    // 初始化收银台
    POS.init();
    // 默认跳转
    navigate('pos');
  }

  // 退出登录
  function logout() {
    API.clearToken();
    state.user = null;
    state.cart = [];
    document.getElementById('main-app').style.display = 'none';
    document.getElementById('login-page').style.display = 'flex';
    document.getElementById('login-pass').value = '';
    Toast.info('已退出登录');
  }

  // ============ 初始化 ============
  async function init() {
    startClock();

    // 检查是否已登录
    if (API.getToken()) {
      try {
        state.user = await API.auth.me();
        enterMain();
        return;
      } catch (e) {
        API.clearToken();
      }
    }

    // 未登录 → 检查健康
    checkHealthBtn();
  }

  // 登录页「检查健康」
  async function checkHealthBtn() {
    const el = document.getElementById('login-health');
    try {
      const r = await API.health.ready();
      el.textContent = `● ${r.status === 'ready' ? '服务正常' : '服务异常'} · License: ${r.license}`;
      el.className = r.status === 'ready' ? 'text-green' : 'text-red';
    } catch (e) {
      el.textContent = '● 无法连接服务';
      el.className = 'text-red';
    }
  }

  // ============ 启动 ============
  document.addEventListener('DOMContentLoaded', init);

  // 暴露全局接口
  window.App = { state, navigate, logout, doLogin };
})();

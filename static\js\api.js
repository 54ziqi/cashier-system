/**
 * API 封装层
 * 自动注入 Token，统一 Toast 错误处理
 *
 * M1 扩展: 桌台管理 / 订单状态机 / 商品规格 / 86 / BOM / 套餐
 */
const API = (() => {
  const BASE = '';

  function getToken() {
    return localStorage.getItem('token') || '';
  }

  async function request(method, path, body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(BASE + path, opts);
    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      const msg = data.detail || `请求失败 (${resp.status})`;
      if (resp.status === 401) {
        throw { status: 401, message: msg };
      }
      Toast.error(msg);
      throw new Error(msg);
    }
    return data;
  }

  return {
    getToken,
    setToken: (t) => localStorage.setItem('token', t),
    clearToken: () => localStorage.removeItem('token'),

    get: (p) => request('GET', p),
    post: (p, b) => request('POST', p, b),
    put: (p, b) => request('PUT', p, b),
    del: (p) => request('DELETE', p),

    // 业务接口
    auth: {
      login: (username, password) => request('POST', '/api/v1/auth/login', { username, password }),
      me: () => request('GET', '/api/v1/auth/me'),
    },
    health: {
      live: () => request('GET', '/health/live'),
      ready: () => request('GET', '/health/ready'),
    },
    products: {
      list: (page = 1, opts = {}) => {
        const params = new URLSearchParams({ page, ...opts });
        return request('GET', `/api/v1/merchant/products?${params}`);
      },
      search: (q) => request('GET', `/api/v1/merchant/products/search?q=${encodeURIComponent(q)}`),
      getByBarcode: (code) => request('GET', `/api/v1/merchant/products/barcode/${encodeURIComponent(code)}`),
      create: (data) => request('POST', '/api/v1/merchant/products', data),
      update: (id, data) => request('PUT', `/api/v1/merchant/products/${id}`, data),
      del: (id) => request('DELETE', `/api/v1/merchant/products/${id}`),
    },
    categories: {
      list: () => request('GET', '/api/v1/merchant/categories'),
      create: (data) => request('POST', '/api/v1/merchant/categories', data),
      update: (id, data) => request('PUT', '/api/v1/merchant/categories/${id}', data),
      del: (id) => request('DELETE', `/api/v1/merchant/categories/${id}`),
    },
    orders: {
      list: (params) => request('GET', `/api/v1/merchant/orders?${new URLSearchParams(params).toString()}`),
      refund: (id) => request('POST', `/api/v1/merchant/orders/refund/${id}`),
    },
    cashier: {
      checkout: (data) => request('POST', '/api/v1/merchant/cashier/checkout', data),
    },
    members: {
      list: () => request('GET', '/api/v1/merchant/members'),
      searchByPhone: (phone) => request('GET', `/api/v1/merchant/members?phone=${phone}`),
      recharge: (id, amount) => request('POST', `/api/v1/merchant/members/${id}/recharge`, { amount }),
      create: (data) => request('POST', '/api/v1/merchant/members', data),
    },

    // ==================== M1 新增 ====================

    /**
     * 桌台管理 API
     */
    tables: {
      /** 列出所有桌台 */
      list: () => request('GET', '/api/v1/merchant/tables'),
      /** 新建桌台 */
      create: (data) => request('POST', '/api/v1/merchant/tables', data),
      /** 开台 (empty → seated) */
      seat: (id) => request('POST', `/api/v1/merchant/tables/${id}/seat`),
      /** 清台 (seated/dirty → empty) */
      clear: (id) => request('POST', `/api/v1/merchant/tables/${id}/clear`),
      /** 预留 (empty → reserved) */
      reserve: (id) => request('POST', `/api/v1/merchant/tables/${id}/reserve`),
      /** 绑定订单到桌台 */
      occupy: (id, orderId) => request('POST', `/api/v1/merchant/tables/${id}/occupy`, { order_id: orderId }),
      /** 更新桌台位置/属性 */
      updateLayout: (id, data) => request('PUT', `/api/v1/merchant/tables/${id}/layout`, data),
      /** 删除桌台 (admin only) */
      delete: (id) => request('DELETE', `/api/v1/merchant/tables/${id}`),
    },

    /**
     * 订单状态机 API
     */
    orderOps: {
      /** 推动订单状态流转 */
      transition: (orderId, transition, extra = {}) =>
        request('POST', `/api/v1/merchant/orders/${orderId}/status`, {
          transition,
          ...extra,
        }),
      /** 整单作废 (admin only) */
      void: (orderId, reason = '') =>
        request('POST', `/api/v1/merchant/orders/${orderId}/void`, { reason }),
      /** 催菜 */
      urge: (orderId) =>
        request('POST', `/api/v1/merchant/orders/${orderId}/urge`),
    },

    /**
     * 商品规格 API
     */
    specs: {
      /** 获取商品规格组与选项 */
      get: (productId) =>
        request('GET', `/api/v1/merchant/products/${productId}/specs`),
      /** 设置商品规格 (全量覆盖) */
      set: (productId, groups, options) =>
        request('POST', `/api/v1/merchant/products/${productId}/specs`, { groups, options }),
    },

    /**
     * 商品沽清 API
     */
    stock: {
      /** 切换86状态 */
      mark86: (productId, is86) =>
        request('POST', `/api/v1/merchant/products/${productId}/86`, { is_86: is86 }),
    },

    /**
     * 商品配方 API
     */
    bom: {
      /** 设置BOM */
      set: (productId, bom) =>
        request('POST', `/api/v1/merchant/products/${productId}/bom`, { bom }),
    },

    /**
     * 商品套餐切换 API
     */
    combo: {
      /** 切换套餐状态 */
      toggle: (productId, isCombo) =>
        request('POST', `/api/v1/merchant/products/${productId}/combo`, { is_combo: isCombo }),
    },
  };
})();

window.API = API;

/**
 * API 封装层
 * 自动注入 Token，统一 Toast 错误处理
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
      // 401 不弹 toast，由调用方处理跳转
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
      update: (id, data) => request('PUT', `/api/v1/merchant/categories/${id}`, data),
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
  };
})();

window.API = API;

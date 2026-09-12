/**
 * 报表模块
 */
const Report = (() => {
  async function onShow() {
    await renderReport();
  }

  async function renderReport() {
    const container = document.querySelector('.report-summary');
    if (!container) return;

    // 显示加载状态
    container.querySelectorAll('.value').forEach(el => el.textContent = '…');

    try {
      const resp = await API.orders.list({ page: '1', page_size: '200' });
      const orders = resp.items || [];

      // 计算今日数据
      const today = new Date().toISOString().slice(0, 10);
      const todayOrders = orders.filter(o => (o.created_at || '').startsWith(today));
      const todayRevenue = todayOrders.reduce((sum, o) => sum + (o.final_amount || 0), 0);
      const avgOrder = todayOrders.length > 0 ? todayRevenue / todayOrders.length : 0;

      // 渲染数据
      const values = container.querySelectorAll('.value');
      if (values[0]) values[0].textContent = '¥' + (todayRevenue / 100).toFixed(2);
      if (values[1]) values[1].textContent = todayOrders.length;
      if (values[2]) values[2].textContent = '¥' + (avgOrder / 100).toFixed(2);
      if (values[3]) values[3].textContent = '—';

    } catch (e) {
      Toast.error('报表加载失败：' + e.message);
    }
  }

  return { onShow };
})();

window.Report = Report;

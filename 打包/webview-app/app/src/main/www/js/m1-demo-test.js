/**
 * M1 Demo / 自测脚本
 * 在浏览器 console 中运行以下函数验证各模块
 */
window.M1Demo = {
  testSpec: () => {
    API.specs.get = async () => ({
      groups: [
        { group_name: '杯型', required: true, min_select: 1, max_select: 1 },
        { group_name: '温度', required: true, min_select: 1, max_select: 1 },
        { group_name: '糖度', required: false, min_select: 0, max_select: 1 },
        { group_name: '加料', required: false, min_select: 0, max_select: 3 },
      ],
      options: [
        { option_name: '杯型', value: '中杯', price_delta: 0 },
        { option_name: '杯型', value: '大杯', price_delta: 400 },
        { option_name: '温度', value: '冰', price_delta: 0 },
        { option_name: '温度', value: '热', price_delta: 0 },
        { option_name: '糖度', value: '全糖', price_delta: 0 },
        { option_name: '糖度', value: '半糖', price_delta: 0 },
        { option_name: '加料', value: '珍珠', price_delta: 300 },
        { option_name: '加料', value: '椰果', price_delta: 300 },
        { option_name: '加料', value: '布丁', price_delta: 500 },
      ],
    });
    SpecModal.open({ id: 'p1', name: '招牌奶茶', price: 1400, icon: '🧋' });
  },
  testReceipt: () => {
    ReceiptRenderer.showModal({
      order_no: 'QH20250913001',
      total: 5800, paid: 5800, change: 0,
      pay_method: 'wechat',
      items: [
        { name: '招牌奶茶', spec_text: '大杯,冰,半糖,珍珠', qty: 2, price: 1800, subtotal: 3600, unit: 'pcs' },
        { name: '炸鸡翅', spec_text: '', qty: 1, price: 2200, subtotal: 2200, unit: 'pcs' },
      ],
      table_name: '3号桌',
      queue_no: 'A01',
    });
  },
  testOrderDetail: () => {
    OrderDetailModal.show({
      order_no: 'QH20250913001',
      order_id: 'ord_001',
      table_name: '3号桌',
      status: 'completed',
      total: 5800,
      items: [
        { name: '招牌奶茶', spec_text: '大杯,冰,半糖', qty: 2, subtotal: 3600 },
        { name: '炸鸡翅', spec_text: '', qty: 1, subtotal: 2200 },
      ],
      created_at: '2025-09-13T14:30:00Z',
      queue_no: 'A01',
    });
  },
  testPickupBanner: () => {
    POS.showPickupBanner('A01');
  },
};

console.log('M1 Demo helpers loaded.');

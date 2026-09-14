import logging

from app.infra.hardware.base import BaseDevice, DeviceInfo

log = logging.getLogger(__name__)


class ReceiptPrinterDriver(BaseDevice):
    """
    小票打印机驱动 (ESC/POS 指令集)
    支持 USB / Serial / Network 连接方式
    """

    def __init__(self, info: DeviceInfo):
        super().__init__(info)
        self._printer = None
        self._vendor_id = info.config.get("vendor_id", 0x0416)
        self._product_id = info.config.get("product_id", 0x5011)
        self._port = info.config.get("port", "/dev/ttyUSB1")
        self._baudrate = info.config.get("baudrate", 19200)
        self._host = info.config.get("host", "")
        self._tcp_port = info.config.get("tcp_port", 9100)

    def connect(self) -> bool:
        try:
            from escpos.printer import Network, Serial, Usb

            conn_type = self.info.connection_type
            if conn_type.value == "usb":
                self._printer = Usb(self._vendor_id, self._product_id)
            elif conn_type.value == "serial":
                self._printer = Serial(self._port, self._baudrate)
            elif conn_type.value == "network":
                self._printer = Network(self._host, self._tcp_port)
            else:
                log.error(f"不支持的连接类型: {conn_type}")
                return False

            self._connected = True
            log.info(f"小票打印机已连接: {conn_type.value}")
            return True
        except ImportError:
            log.error("请安装 python-escpos: pip install python-escpos")
            return False
        except Exception as e:
            log.error(f"打印机连接失败: {e}")
            return False

    def disconnect(self) -> None:
        if self._printer:
            try:
                self._printer.close()
            except Exception:
                pass
            self._printer = None
        self._connected = False
        log.info("小票打印机已断开")

    def is_connected(self) -> bool:
        return self._connected

    def print_receipt(self, order_data: dict, shop_config: dict) -> bool:
        """打印小票"""
        if not self._printer:
            log.error("打印机未连接")
            return False

        try:
            p = self._printer

            # 店铺名称
            p.set(align="center", bold=True, double_height=True, double_width=True)
            p.text(f"{shop_config.get('name', 'Cashier')}\n\n")

            # 订单信息
            p.set(align="left", bold=False)
            p.text(f"订单号: {order_data.get('order_no', '')}\n")
            p.text(f"时间: {order_data.get('created_at', '')}\n")
            p.text(f"收银员: {order_data.get('cashier_name', '')}\n")
            p.text("-" * 32 + "\n")

            # 商品明细
            for item in order_data.get("items", []):
                name = item.get("name", "")
                qty = item.get("qty", 1)
                price = item.get("price", 0)
                subtotal = item.get("subtotal", 0)
                p.text(f"{name[:16]}\n")
                p.text(f"  {qty} x {price:.2f} = {subtotal:.2f}\n")

            p.text("-" * 32 + "\n")

            # 合计
            p.set(align="right", bold=True)
            p.text(f"合计: {order_data.get('total', 0):.2f}\n")

            discount = order_data.get("discount", 0)
            if discount > 0:
                p.text(f"折扣: -{discount:.2f}\n")

            p.text(f"实付: {order_data.get('final', 0):.2f}\n")

            # 支付方式
            p.set(align="left", bold=False)
            p.text(f"支付方式: {order_data.get('pay_method', '')}\n")

            if order_data.get("member_name"):
                p.text(
                    f"会员: {order_data.get('member_name')} (积分+{order_data.get('points_earned', 0)})\n"
                )

            p.text("\n\n")
            p.set(align="center")
            p.text("谢谢惠顾，欢迎下次光临！\n")
            p.text("\n\n\n")

            # 切纸
            p.cut()
            return True

        except Exception as e:
            log.error(f"打印失败: {e}")
            return False

    def open_cash_drawer(self) -> bool:
        """开钱箱 (DLE, ESC, p)"""
        if not self._printer:
            return False
        try:
            # ESC p 0 25 250 - 钱箱开启指令
            self._printer._raw(b"\x1b\x70\x00\x19\xfa")
            return True
        except Exception as e:
            log.error(f"开钱箱失败: {e}")
            return False

    def test_page(self) -> bool:
        """打印测试页"""
        if not self._printer:
            return False
        try:
            self._printer.set(align="center", bold=True)
            self._printer.text("Cashier Test Page\n\n")
            self._printer.text("Printer OK\n")
            self._printer.text("\n\n\n")
            self._printer.cut()
            return True
        except Exception as e:
            log.error(f"测试页打印失败: {e}")
            return False

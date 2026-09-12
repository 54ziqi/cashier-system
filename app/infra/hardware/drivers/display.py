import logging

from app.infra.hardware.base import BaseDevice, DeviceInfo

log = logging.getLogger(__name__)


class CustomerDisplayDriver(BaseDevice):
    """
    顾客显示屏 / 收款码屏幕
    通过原生 JS WebSocket 实现
    也可通过串口 LED8 显示屏驱动
    """

    def __init__(self, info: DeviceInfo):
        super().__init__(info)
        self._display_mode = info.config.get("mode", "websocket")
        self._port = info.config.get("port", "")
        self._ser = None

    def connect(self) -> bool:
        if self._display_mode == "serial":
            return self._connect_serial()
        self._connected = True
        log.info("WebSocket客显已就绪")
        return True

    def _connect_serial(self) -> bool:
        try:
            import serial

            self._ser = serial.Serial(port=self._port, baudrate=9600, timeout=0.5)
            self._connected = True
            log.info(f"串口客显已连接: {self._port}")
            return True
        except Exception as e:
            log.error(f"串口客显连接失败: {e}")
            return False

    def disconnect(self) -> None:
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self._connected = False
        log.info("客显已断开")

    def is_connected(self) -> bool:
        return self._connected

    def display_item(self, name: str, price: float, qty: float) -> None:
        """显示当前扫描商品"""
        if self._display_mode == "serial" and self._ser:
            self._send_serial(f"{name[:8]} {price:.2f}x{qty}")
        self._notify(
            {
                "action": "display_item",
                "name": name,
                "price": price,
                "qty": qty,
            }
        )

    def display_total(self, total: float, item_count: int) -> None:
        """显示合计"""
        if self._display_mode == "serial" and self._ser:
            self._send_serial(f"TOTAL {total:.2f}")
        self._notify(
            {
                "action": "display_total",
                "total": total,
                "item_count": item_count,
            }
        )

    def show_qrcode(self, qr_data: dict) -> None:
        """显示收款码信息"""
        self._notify(
            {
                "action": "show_qrcode",
                "qr_url": qr_data.get("qr_url", ""),
                "amount": qr_data.get("amount", 0),
                "expire_at": qr_data.get("expire_at", 0),
            }
        )

    def show_payment_success(self, duration: int = 3) -> None:
        """显示支付成功"""
        if self._display_mode == "serial" and self._ser:
            self._send_serial("PAID SUCCESS!")
        self._notify(
            {
                "action": "payment_success",
                "duration": duration,
            }
        )

    def clear(self) -> None:
        """清屏"""
        if self._display_mode == "serial" and self._ser:
            self._ser.write(b"\x0c")
        self._notify({"action": "clear"})

    def _send_serial(self, text: str) -> None:
        """发送文本到串口显示屏"""
        try:
            if self._ser:
                self._ser.write(b"\x0c")
                self._ser.write(text[:16].encode("gbk", errors="ignore"))
        except Exception as e:
            log.error(f"串口发送失败: {e}")

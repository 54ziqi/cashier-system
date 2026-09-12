import logging
import threading
import time

from app.infra.hardware.base import BaseDevice, DeviceInfo

log = logging.getLogger(__name__)


class SerialScannerDriver(BaseDevice):
    """USB-CDC / RS232 串口扫码枪驱动"""

    def __init__(self, info: DeviceInfo):
        super().__init__(info)
        self._port = info.config.get("port", "/dev/ttyUSB0")
        self._baudrate = info.config.get("baudrate", 9600)
        self._ser = None
        self._thread = None
        self._running = False

    def connect(self) -> bool:
        try:
            import serial

            self._ser = serial.Serial(
                port=self._port, baudrate=self._baudrate, timeout=0.1
            )
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            self._connected = True
            log.info(f"扫码枪已连接: {self._port}")
            return True
        except ImportError:
            log.error("请安装 pyserial: pip install pyserial")
            return False
        except Exception as e:
            log.error(f"扫码枪连接失败: {e}")
            return False

    def disconnect(self) -> None:
        self._running = False
        if self._ser:
            self._ser.close()
            self._ser = None
        self._connected = False
        log.info("扫码枪已断开")

    def is_connected(self) -> bool:
        return self._connected

    def _read_loop(self):
        buffer = ""
        while self._running and self._ser:
            try:
                data = self._ser.read(self._ser.in_waiting or 1)
                if data:
                    char = data.decode("utf-8", errors="ignore")
                    if char in ("\r", "\n"):
                        if buffer:
                            barcode = buffer.strip()
                            log.info(f"扫码: {barcode}")
                            self._notify({"type": "barcode", "code": barcode})
                            buffer = ""
                    else:
                        buffer += char
            except Exception as e:
                log.error(f"扫码枪读取错误: {e}")
                time.sleep(1)


class HIDScannerDriver(BaseDevice):
    """
    USB-HID 键盘模拟扫码枪
    通过 evdev 监听 Linux 输入事件（可选实现）
    """

    def __init__(self, info: DeviceInfo):
        super().__init__(info)
        self._device_path = info.config.get("device_path", "")

    def connect(self) -> bool:
        try:
            import evdev

            if self._device_path:
                self._device = evdev.InputDevice(self._device_path)
            else:
                devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
                for dev in devices:
                    if "scanner" in dev.name.lower() or "barcode" in dev.name.lower():
                        self._device = dev
                        break
                else:
                    log.warning("未找到扫码枪设备")
                    return False
            self._connected = True
            log.info(f"HID扫码枪已连接: {self._device.name}")
            return True
        except ImportError:
            log.warning("请安装 evdev: pip install evdev")
            return False
        except Exception as e:
            log.error(f"HID扫码枪连接失败: {e}")
            return False

    def disconnect(self) -> None:
        self._connected = False
        log.info("HID扫码枪已断开")

    def is_connected(self) -> bool:
        return self._connected

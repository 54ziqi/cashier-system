import logging
import threading
import time

from app.infra.hardware.base import ScaleCallback, BaseDevice, DeviceInfo

log = logging.getLogger(__name__)


class SerialScaleDriver(BaseDevice):
    """
    电子秤串口驱动
    支持连续输出模式和命令读取模式
    """

    PROTOCOLS = {
        "continuous": {
            "frame_len": 22,
            "weight_start": 3,
            "weight_end": 9,
            "stable_flag_idx": 2,
            "stable_value": ord("S"),
            "unit": "g",
        },
        "kaifeng": {
            "frame_len": 17,
            "weight_start": 2,
            "weight_end": 8,
            "stable_flag_idx": 1,
            "stable_value": ord("S"),
            "unit": "g",
        },
        "yongli": {
            "frame_len": 26,
            "weight_start": 4,
            "weight_end": 10,
            "stable_flag_idx": 3,
            "stable_value": ord("S"),
            "unit": "kg",
        },
    }

    def __init__(self, info: DeviceInfo):
        super().__init__(info)
        self._port = info.config.get("port", "/dev/ttyUSB2")
        self._baudrate = info.config.get("baudrate", 9600)
        self._protocol = info.config.get("protocol", "continuous")
        self._ser = None
        self._thread = None
        self._running = False
        self._last_weight = 0.0
        self._is_stable = False
        self._tare_weight = 0.0

    def connect(self) -> bool:
        try:
            import serial
            self._ser = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            self._connected = True
            log.info(f"电子秤已连接: {self._port}")
            return True
        except ImportError:
            log.error("请安装 pyserial: pip install pyserial")
            return False
        except Exception as e:
            log.error(f"电子秤连接失败: {e}")
            return False

    def disconnect(self) -> None:
        self._running = False
        if self._ser:
            self._ser.close()
            self._ser = None
        self._connected = False
        log.info("电子秤已断开")

    def is_connected(self) -> bool:
        return self._connected

    @property
    def current_weight(self) -> float:
        """返回去皮后的净重 (kg)"""
        return max(self._last_weight - self._tare_weight, 0.0)

    @property
    def is_stable(self) -> bool:
        return self._is_stable

    def tare(self) -> None:
        """去皮"""
        self._tare_weight = self._last_weight
        log.info(f"已去皮: {self._tare_weight:.3f}kg")

    def zero(self) -> None:
        """清零"""
        try:
            if self._ser:
                self._ser.write(b"\x1b\x70\x00")
                log.info("已清零")
        except Exception as e:
            log.error(f"清零失败: {e}")

    def _read_loop(self):
        cfg = self.PROTOCOLS.get(self._protocol, self.PROTOCOLS["continuous"])
        frame_len = cfg.get("frame_len", 22)

        while self._running and self._ser:
            try:
                if self._ser.in_waiting >= frame_len:
                    frame = self._ser.read(frame_len)
                    weight = self._parse_frame(frame, cfg)
                    if weight is not None:
                        self._last_weight = weight
                        self._notify({
                            "type": "weight",
                            "weight": self.current_weight,
                            "raw": weight,
                            "stable": self._is_stable,
                            "tare": self._tare_weight,
                        })
                else:
                    time.sleep(0.05)
            except Exception as e:
                log.error(f"电子秤读取错误: {e}")
                time.sleep(1)

    def _parse_frame(self, frame: bytes, cfg: dict) -> float | None:
        try:
            ws = cfg.get("weight_start", 3)
            we = cfg.get("weight_end", 9)
            weight_str = frame[ws:we].decode("ascii", errors="ignore").strip()

            if not weight_str or not weight_str.replace(".", "").replace("-", "").isdigit():
                return None

            weight_val = float(weight_str)

            if cfg.get("unit") == "g":
                weight_val /= 1000.0

            sf_idx = cfg.get("stable_flag_idx", 2)
            sf_val = cfg.get("stable_value", ord("S"))
            self._is_stable = frame[sf_idx] == sf_val

            return weight_val

        except (ValueError, IndexError):
            return None

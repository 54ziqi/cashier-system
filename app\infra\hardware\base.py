"""硬件抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DeviceType(str, Enum):
    SCANNER = "scanner"
    PRINTER = "printer"
    SCALE = "scale"
    DISPLAY = "display"
    CASH_DRAWER = "cash_drawer"


class ConnectionType(str, Enum):
    USB_HID = "usb_hid"
    USB_CDC = "usb_cdc"
    SERIAL = "serial"
    NETWORK = "network"
    BLUETOOTH = "bluetooth"


@dataclass
class DeviceInfo:
    device_id: str
    device_type: DeviceType
    name: str
    connection_type: ConnectionType
    config: dict[str, Any]
    status: str = "offline"


class BaseDevice(ABC):
    """硬件设备抽象基类"""

    def __init__(self, info: DeviceInfo):
        self.info = info
        self._connected = False
        self._callbacks: list[Callable] = []

    @abstractmethod
    def connect(self) -> bool:
        """连接设备"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开设备"""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        ...

    def register_callback(self, callback: Callable) -> None:
        """注册数据回调"""
        self._callbacks.append(callback)

    def _notify(self, data: Any) -> None:
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(data)
            except Exception:
                pass


class ScannerCallback:
    """扫码枪回调接口"""

    def on_barcode(self, barcode: str) -> None:
        raise NotImplementedError


class ScaleCallback:
    """电子秤回调接口"""

    def on_weight(self, weight: float, is_stable: bool) -> None:
        raise NotImplementedError

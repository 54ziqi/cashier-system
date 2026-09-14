"""硬件设备注册表"""

from __future__ import annotations

import logging
from threading import Lock

from .base import BaseDevice, DeviceType

log = logging.getLogger(__name__)


class DeviceRegistry:
    """线程安全的硬件设备注册表"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._devices = {}
            return cls._instance

    def register(self, device: BaseDevice) -> None:
        """注册设备"""
        key = f"{device.info.device_type.value}:{device.info.device_id}"
        self._devices[key] = device
        log.info(f"设备已注册: {key}")

    def unregister(self, device_type: DeviceType, device_id: str) -> None:
        """注销设备"""
        key = f"{device_type.value}:{device_id}"
        if key in self._devices:
            device = self._devices.pop(key)
            device.disconnect()
            log.info(f"设备已注销: {key}")

    def get(self, device_type: DeviceType, device_id: str) -> BaseDevice | None:
        """获取设备"""
        key = f"{device_type.value}:{device_id}"
        return self._devices.get(key)

    def get_by_type(self, device_type: DeviceType) -> list[BaseDevice]:
        """按类型获取设备"""
        return [d for d in self._devices.values() if d.info.device_type == device_type]

    def all_devices(self) -> list[BaseDevice]:
        """获取所有设备"""
        return list(self._devices.values())

    def get_scanner(self) -> BaseDevice | None:
        """获取第一个扫码枪设备"""
        devices = self.get_by_type(DeviceType.SCANNER)
        return devices[0] if devices else None

    def get_printer(self) -> BaseDevice | None:
        """获取第一个打印机设备"""
        devices = self.get_by_type(DeviceType.PRINTER)
        return devices[0] if devices else None

    def get_scale(self) -> BaseDevice | None:
        """获取第一个电子秤设备"""
        devices = self.get_by_type(DeviceType.SCALE)
        return devices[0] if devices else None

    def get_display(self) -> BaseDevice | None:
        """获取第一个显示设备"""
        devices = self.get_by_type(DeviceType.DISPLAY)
        return devices[0] if devices else None


registry = DeviceRegistry()

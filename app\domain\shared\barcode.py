"""Barcode 值对象 - 条码验证"""

from __future__ import annotations

import re


class Barcode(str):
    """条码值对象"""

    def __new__(cls, value: str) -> Barcode:
        cleaned = cls._clean(value)
        if not cls._is_valid(cleaned):
            raise ValueError(f"无效条码: {value}")
        return super().__new__(cls, cleaned)

    @staticmethod
    def _clean(value: str) -> str:
        return value.strip()

    @staticmethod
    def _is_valid(barcode: str) -> bool:
        if not barcode or len(barcode) > 32:
            return False
        return bool(re.match(r"^[0-9A-Za-z\-_\.\/\+]+$", barcode))

    @property
    def is_upc(self) -> bool:
        """是否为 UPC/EAN 码"""
        return self.isdigit() and len(self) in (8, 12, 13)

    @property
    def is_internal(self) -> bool:
        """是否为内部码（以20-29开头）"""
        return self[:2].isdigit() and 20 <= int(self[:2]) <= 29

"""Money 值对象 - 金额计算精确到分"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Money:
    """金额值对象，内部以分为单位存储"""
    cents: int

    @classmethod
    def from_yuan(cls, yuan: Union[int, float, str]) -> "Money":
        """从元创建金额"""
        if isinstance(yuan, str):
            yuan = float(yuan)
        return cls(int(round(float(yuan) * 100)))

    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        """从分创建金额"""
        return cls(cents)

    @classmethod
    def zero(cls) -> "Money":
        return cls(0)

    def to_yuan(self) -> float:
        """返回元的浮点值"""
        return self.cents / 100.0

    def to_yuan_str(self) -> str:
        """返回元的字符串表示"""
        return f"{self.to_yuan():.2f}"

    def __add__(self, other: "Money") -> "Money":
        return Money(self.cents + other.cents)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.cents - other.cents)

    def __mul__(self, factor: Union[int, float]) -> "Money":
        return Money(int(round(self.cents * factor)))

    def __lt__(self, other: "Money") -> bool:
        return self.cents < other.cents

    def __le__(self, other: "Money") -> bool:
        return self.cents <= other.cents

    def __gt__(self, other: "Money") -> bool:
        return self.cents > other.cents

    def __ge__(self, other: "Money") -> bool:
        return self.cents >= other.cents

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return False
        return self.cents == other.cents

    def __repr__(self) -> str:
        return f"Money({self.to_yuan_str()})"


def apply_discount(amount: Money, discount_ratio: float) -> Money:
    """应用折扣"""
    discounted = int(round(amount.cents * (1 - discount_ratio)))
    return Money(max(discounted, 0))

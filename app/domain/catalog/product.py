"""领域层：商品聚合根"""
from __future__ import annotations


class Product:
    """商品聚合根"""

    def __init__(self, id: str, merchant_id: str, name: str, price: int,
                 barcode: str = "", category_id: str = "", cost_price: int = 0,
                 stock: float = 0, unit: str = "pcs", is_weighing: bool = False,
                 icon: str = "📦", status: str = "active"):
        self.id = id
        self.merchant_id = merchant_id
        self.name = name
        self.price = price  # 分
        self.barcode = barcode
        self.category_id = category_id
        self.cost_price = cost_price
        self.stock = stock
        self.unit = unit
        self.is_weighing = is_weighing
        self.icon = icon
        self.status = status

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def update_price(self, new_price: int) -> None:
        if new_price < 0:
            raise ValueError("Price cannot be negative")
        self.price = new_price

    def update_stock(self, new_stock: float) -> None:
        self.stock = max(new_stock, 0)

    def reduce_stock(self, qty: float) -> None:
        if self.stock < qty:
            raise ValueError(f"Insufficient stock: {self.stock} < {qty}")
        self.stock -= qty

    def check_stock(self, qty: float = 1) -> bool:
        return self.stock >= qty

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "name": self.name,
            "price": self.price,
            "price_yuan": round(self.price / 100, 2),
            "barcode": self.barcode,
            "category_id": self.category_id,
            "cost_price": self.cost_price,
            "stock": self.stock,
            "unit": self.unit,
            "is_weighing": self.is_weighing,
            "icon": self.icon,
            "status": self.status,
        }

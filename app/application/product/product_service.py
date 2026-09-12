"""应用层：商品服务"""

from __future__ import annotations

import logging
import uuid

from app.infra.db.engine import session_factory
from app.infra.db.models import Product as ProductModel

log = logging.getLogger(__name__)


def _escape_like(value: str) -> str:
    """转义 LIKE 特殊字符：\\、%、_"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ProductService:
    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def list_products(
        self,
        page: int = 1,
        page_size: int = 50,
        status: str = "",
        category_id: str = "",
        q: str = "",
    ) -> dict:
        with session_factory() as s:
            query = s.query(ProductModel).filter_by(merchant_id=self.merchant_id)
            if status:
                query = query.filter_by(status=status)
            if category_id:
                query = query.filter_by(category_id=category_id)
            if q:
                escaped = _escape_like(q)
                query = query.filter(
                    ProductModel.name.like(f"%{escaped}%", escape="\\")
                )
            total = query.count()
            items = (
                query.order_by(ProductModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._to_dict(p) for p in items],
            }

    def get_product(self, product_id: str) -> dict | None:
        with session_factory() as s:
            p = (
                s.query(ProductModel)
                .filter_by(id=product_id, merchant_id=self.merchant_id)
                .first()
            )
            return self._to_dict(p) if p else None

    def get_by_barcode(self, barcode: str) -> dict | None:
        with session_factory() as s:
            p = (
                s.query(ProductModel)
                .filter_by(
                    merchant_id=self.merchant_id, barcode=barcode, status="active"
                )
                .first()
            )
            return self._to_dict(p) if p else None

    def search(self, q: str, limit: int = 20) -> list[dict]:
        with session_factory() as s:
            items = (
                s.query(ProductModel)
                .filter(
                    ProductModel.merchant_id == self.merchant_id,
                    ProductModel.status == "active",
                    ProductModel.name.like(f"%{_escape_like(q)}%", escape="\\"),
                )
                .limit(limit)
                .all()
            )
            return [self._to_dict(p) for p in items]

    def create_product(self, data: dict) -> dict:
        with session_factory() as s:
            product = ProductModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=data["name"],
                price=data["price"],
                barcode=data.get("barcode", ""),
                category_id=data.get("category_id", ""),
                cost_price=data.get("cost_price", 0),
                stock=float(data.get("stock", 0)),
                unit=data.get("unit", "pcs"),
                is_weighing=1 if data.get("is_weighing") else 0,
                icon=data.get("icon", "📦"),
            )
            s.add(product)
            s.commit()
            log.info(f"Product created: {product.name} ({product.id})")
            return self._to_dict(product)

    def update_product(self, product_id: str, data: dict) -> dict | None:
        with session_factory() as s:
            p = (
                s.query(ProductModel)
                .filter_by(id=product_id, merchant_id=self.merchant_id)
                .first()
            )
            if not p:
                return None
            for field in [
                "name",
                "price",
                "barcode",
                "category_id",
                "cost_price",
                "stock",
                "unit",
                "icon",
                "status",
            ]:
                if field in data:
                    setattr(p, field, data[field])
            if "is_weighing" in data:
                p.is_weighing = 1 if data["is_weighing"] else 0
            s.commit()
            return self._to_dict(p)

    def delete_product(self, product_id: str) -> None:
        with session_factory() as s:
            p = (
                s.query(ProductModel)
                .filter_by(id=product_id, merchant_id=self.merchant_id)
                .first()
            )
            if p:
                p.status = "inactive"
                s.commit()

    def _to_dict(self, p) -> dict:
        if not p:
            return {}
        return {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "price_yuan": round(p.price / 100, 2),
            "barcode": p.barcode,
            "category_id": p.category_id,
            "cost_price": p.cost_price,
            "stock": p.stock,
            "unit": p.unit,
            "is_weighing": bool(p.is_weighing),
            "icon": p.icon,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }

    def seed_demo_products(self) -> int:
        """首次启动时写入示例商品"""
        demo = [
            ("红富士苹果", 500, "🍎", "斤", True),
            ("可口可乐", 350, "🥤", "瓶", False),
            ("切片面包", 800, "🍞", "袋", False),
            ("鲜牛奶1L", 600, "🥛", "盒", False),
            ("乐事薯片", 750, "🍟", "包", False),
            ("芝士片", 1200, "🧀", "盒", False),
            ("鲜鸡蛋", 1500, "🥚", "斤", True),
            ("橙子", 450, "🍊", "斤", True),
            ("香蕉", 300, "🍌", "斤", True),
            ("矿泉水", 200, "💧", "瓶", False),
            ("酸奶", 400, "🥛", "杯", False),
            ("饼干", 650, "🍪", "包", False),
            ("牛肉干", 2500, "🥩", "包", False),
            ("巧克力", 990, "🍫", "块", False),
            ("方便面", 450, "🍜", "袋", False),
            ("纸巾", 300, "🧻", "包", False),
        ]
        with session_factory() as s:
            existing = (
                s.query(ProductModel).filter_by(merchant_id=self.merchant_id).count()
            )
            if existing > 0:
                return 0
            for i, (name, price, icon, unit, weighing) in enumerate(demo):
                p = ProductModel(
                    id=f"demo_p{i + 1:03d}",
                    merchant_id=self.merchant_id,
                    name=name,
                    price=price,
                    barcode=str(1000000 + i),
                    icon=icon,
                    unit=unit,
                    stock=999.0,
                    is_weighing=1 if weighing else 0,
                )
                s.add(p)
            s.commit()
            log.info(f"Seeded {len(demo)} demo products")
            return len(demo)

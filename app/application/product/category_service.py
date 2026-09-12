"""应用层：商品分类服务"""
from __future__ import annotations
import logging
import uuid

from app.infra.db.models import Category as CategoryModel
from app.infra.db.engine import session_factory

log = logging.getLogger(__name__)


class CategoryService:
    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    def list_categories(self) -> list[dict]:
        """列出所有分类"""
        with session_factory() as s:
            items = s.query(CategoryModel).filter_by(
                merchant_id=self.merchant_id
            ).order_by(CategoryModel.sort_order).all()
            return [self._to_dict(c) for c in items]

    def get_category(self, category_id: str) -> dict | None:
        with session_factory() as s:
            c = s.query(CategoryModel).filter_by(
                id=category_id, merchant_id=self.merchant_id
            ).first()
            return self._to_dict(c) if c else None

    def create_category(self, data: dict) -> dict:
        with session_factory() as s:
            cat = CategoryModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                name=data["name"],
                parent_id=data.get("parent_id", "") or None,
                sort_order=int(data.get("sort_order", 0)),
            )
            s.add(cat)
            s.commit()
            log.info(f"Category created: {cat.name} ({cat.id})")
            return self._to_dict(cat)

    def update_category(self, cat_id: str, data: dict) -> dict | None:
        with session_factory() as s:
            c = s.query(CategoryModel).filter_by(
                id=cat_id, merchant_id=self.merchant_id
            ).first()
            if not c:
                return None
            if "name" in data:
                c.name = data["name"]
            if "parent_id" in data:
                c.parent_id = data["parent_id"] or None
            if "sort_order" in data:
                c.sort_order = int(data["sort_order"])
            s.commit()
            return self._to_dict(c)

    def delete_category(self, cat_id: str) -> bool:
        with session_factory() as s:
            c = s.query(CategoryModel).filter_by(
                id=cat_id, merchant_id=self.merchant_id
            ).first()
            if not c:
                return False
            s.delete(c)
            s.commit()
            return True

    def seed_demo_categories(self) -> int:
        """写入示例分类"""
        demo = [
            ("水果", 0),
            ("饮料", 1),
            ("零食", 2),
            ("乳制品", 3),
            ("烘焙", 4),
            ("日用", 5),
        ]
        with session_factory() as s:
            existing = s.query(CategoryModel).filter_by(merchant_id=self.merchant_id).count()
            if existing > 0:
                return 0
            for name, order in demo:
                s.add(CategoryModel(
                    id=str(uuid.uuid4()),
                    merchant_id=self.merchant_id,
                    name=name,
                    sort_order=order,
                ))
            s.commit()
            log.info(f"Seeded {len(demo)} demo categories")
            return len(demo)

    def _to_dict(self, c) -> dict:
        if not c:
            return {}
        return {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "sort_order": c.sort_order,
        }

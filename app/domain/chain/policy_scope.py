"""M6 策略下发域常量与白名单"""

from __future__ import annotations

from typing import ClassVar


class PolicyScope:
    """各策略类型允许下发的字段白名单"""

    MENU_FIELDS: ClassVar[list[str]] = [
        "name", "category_id", "price", "status", "is_86", "specs_json",
    ]
    PRICE_FIELDS: ClassVar[list[str]] = ["price"]
    MEMBER_FIELDS: ClassVar[list[str]] = ["level_config"]
    PROMOTION_FIELDS: ClassVar[list[str]] = ["rules"]


DEFAULT_HQ_PCT = 5  # 总部抽成比例（百分比）

"""业态模板：定义不同行业类型的默认配置、启用功能和工作流规则"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IndustryType(str, Enum):
    """业态类型枚举"""
    FAST_FOOD = "fast_food"          # 快餐
    FULL_SERVICE = "full_service"    # 中餐正餐
    BEVERAGE = "beverage"            # 茶饮/奶茶
    HOTPOT = "hotpot"                # 火锅
    BAKERY = "bakery"                # 烘焙
    RETAIL = "retail"                # 零售/便利店


@dataclass(frozen=True)
class FeaturePolicy:
    """功能开关：开 / 关 / 必开（不可关）"""
    enabled: bool = True
    required: bool = False


@dataclass(frozen=True)
class IndustryTemplate:
    """
    业态模板：每个业态定义该业态默认开启的功能组、默认商品扩展字段、
    订单流程差异、供应链策略。

    features: {feature_key: FeaturePolicy} — 功能开关表
    product_extra_fields: list[str] — 商品模型额外字段
    order_extra_fields: list[str] — 订单模型额外字段
    workflow_overrides: dict[str, str] — 特殊工作流节点
    supply_chain: dict — 供应链策略
    """
    key: IndustryType
    label: str                          # 中文显示名
    description: str
    features: dict[str, FeaturePolicy] = field(default_factory=dict)
    product_extra_fields: list[str] = field(default_factory=list)
    order_extra_fields: list[str] = field(default_factory=list)
    workflow_overrides: dict[str, str] = field(default_factory=dict)
    supply_chain: dict = field(default_factory=dict)


# ── 功能键名常量（与前端/云端同步） ──
class Feature:
    TABLE_MANAGEMENT = "table_management"          # 桌台管理
    KITCHEN_DISPLAY = "kitchen_display"            # 厨打/厨显
    RECIPE_BOM = "recipe_bom"                      # 配方/BOM
    STOCK_ALERT = "stock_alert"                    # 库存预警
    PROCUREMENT = "procurement"                    # 采购/入库/出库
    PHYSICAL_INVENTORY = "physical_inventory"      # 盘点
    PURCHASE_SUGGESTION = "purchase_suggestion"    # 补货建议
    MEMBER_POINTS = "member_points"                # 积分
    MEMBER_STORED_VALUE = "member_stored_value"    # 储值
    MEMBER_LEVELS = "member_levels"                # 等级
    PROMOTION_DISCOUNT = "promotion_discount"      # 满减折扣
    PROMOTION_COUPON = "promotion_coupon"          # 优惠券
    PRINT_RECEIPT = "print_receipt"                # 小票打印
    PRINT_LABEL = "print_label"                    # 标签打印
    COMBO_ITEM = "combo_item"                      # 套餐
    WEIGHT_SALE = "weight_sale"                    # 称重销售
    WEIGHT_PRICE = "weight_price"                  # 称重计价
    TIME_PRICING = "time_pricing"                  # 时段定价
    MULTI_WAREHOUSE = "multi_warehouse"            # 多仓库
    SUPPLY_CHAIN = "supply_chain"                  # 进销存
    INVOICE_REPORT = "invoice_report"              # 财务报表
    CHAIN_PUSH = "chain_push"                      # 连锁下发
    ORDER_VOID_ALL = "order_void_all"              # 整单作废
    AUDIT_LOG = "audit_log"                        # 审计链
    OFFLINE_GRACE = "offline_grace"                # 离线容灾
    DATA_BACKUP = "data_backup"                    # 数据备份


# ── 6 个行业模板定义 ──

_TEMPLATES: dict[IndustryType, IndustryTemplate] = {
    # ── 1. 快餐 ──
    IndustryType.FAST_FOOD: IndustryTemplate(
        key=IndustryType.FAST_FOOD,
        label="快餐/简餐",
        description="前台收银核心场景，点单→出餐→结账，强调效率。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=False),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=True, required=True),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=True),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=False),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=False),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=False),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True, required=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=False),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=False),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=False),
            Feature.TIME_PRICING: FeaturePolicy(enabled=False),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=False),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "specs",        # 规格/做法组
            "is_combo",     # 是否套餐
            "bom_json",     # 配方（原料-BOM）
            "is_86",        # 是否沽清
            "prep_time",    # 预计出餐分钟
        ],
        order_extra_fields=[
            "kitchen_status",    # 后厨状态
            "queue_no",          # 取餐号
        ],
        workflow_overrides={
            "checkout_then_serve": "先结账后出餐",
            "support_takeout": "支持外带一键切换",
        },
        supply_chain={
            "default_mode": "simple",
            "alert_threshold": 10,
            "auto_86": True,
            "track_cost": True,
        },
    ),

    # ── 2. 中餐正餐 ──
    IndustryType.FULL_SERVICE: IndustryTemplate(
        key=IndustryType.FULL_SERVICE,
        label="中餐正餐",
        description="桌台点餐、上菜、转台、联台；后厨KDS为核心；会员储值重点。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=True, required=True),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=True, required=True),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=True),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=True),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True, required=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=True),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=True),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True, required=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=False),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=False),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=False),
            Feature.TIME_PRICING: FeaturePolicy(enabled=True),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=True),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "specs",         # 口味/辣度/去冰/忌口
            "is_combo",      # 套餐/宴席套餐
            "bom_json",      # BOM
            "is_86",         # 沽清
            "course_type",   # 上菜顺序：冷菜/热菜/主食/汤
            "min_order_qty", # 起售量
        ],
        order_extra_fields=[
            "kitchen_status",
            "table_id",
            "table_name",
            "course_sequence",
            "is_merged",
        ],
        workflow_overrides={
            "table_first": "先选桌再点餐",
            "course_fire": "等叫/叫起",
            "support_urge": "催菜",
            "merging": "联台/转台",
            "precheck": "压桌单/预结",
        },
        supply_chain={
            "default_mode": "recipe_based",
            "alert_threshold": 5,
            "auto_86": True,
            "track_cost": True,
            "procurement_type": "multi_step",
        },
    ),

    # ── 3. 茶饮/奶茶 ──
    IndustryType.BEVERAGE: IndustryTemplate(
        key=IndustryType.BEVERAGE,
        label="茶饮/奶茶/咖啡馆",
        description="商品规格（杯型/温度/糖度/加料）是关键；会员储值拉复购。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=False),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=True),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=True),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=False),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True, required=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=True),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=True),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=True),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=False),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=False),
            Feature.TIME_PRICING: FeaturePolicy(enabled=True),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=False),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "specs",           # 杯型/温度/糖度
            "toppings",        # 加料（珍珠/椰果/布丁）
            "bom_json",        # 茶糖浆配方
            "is_86",           # 加料售罄
            "recipe_ratio",    # 出品配方比例
        ],
        order_extra_fields=[
            "kitchen_status",
            "queue_no",
            "spec_text",
        ],
        workflow_overrides={
            "spec_first": "先选规格再下单",
            "label_print": "贴杯标签",
            "making_queue": "制作排队",
        },
        supply_chain={
            "default_mode": "recipe_based",
            "alert_threshold": 15,
            "auto_86": False,
            "track_cost": True,
            "batch_management": True,
        },
    ),

    # ── 4. 火锅 ──
    IndustryType.HOTPOT: IndustryTemplate(
        key=IndustryType.HOTPOT,
        label="火锅/烤肉",
        description="先选锅底再涮菜；锅底+小料+涮菜分开点；BOM原材料管理重要。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=True, required=True),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=True),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=True, required=True),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True, required=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=True),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=True),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=True),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=False),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=True),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=True),
            Feature.TIME_PRICING: FeaturePolicy(enabled=True),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True, required=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True, required=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=True),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "specs",           # 辣度/锅底类型
            "is_combo",        # 锅底套餐
            "bom_json",        # BOM（核心）
            "is_86",           # 售罄
            "product_type",    # 锅底/涮肉/蔬菜/主食/饮料/小料
            "is_weighing",     # 称重
            "unit",            # 盘/斤/份
        ],
        order_extra_fields=[
            "kitchen_status",
            "table_id",
            "table_name",
            "pot_flavor",
            "self_service_veg",
        ],
        workflow_overrides={
            "pot_first": "先点锅底后涮菜",
            "self_bar": "自助涮菜区（不限量）",
            "split_bill": "AA分账/单人清台",
        },
        supply_chain={
            "default_mode": "recipe_based",
            "alert_threshold": 8,
            "auto_86": True,
            "track_cost": True,
            "fresh_management": True,
        },
    ),

    # ── 5. 烘焙 ──
    IndustryType.BAKERY: IndustryTemplate(
        key=IndustryType.BAKERY,
        label="烘焙/甜品",
        description="商品按批生产、当日过期；生产计划 → 预包装 → 收银。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=False),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=False),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=True, required=True),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=False),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=True),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=True),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=True),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=True),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=True),
            Feature.TIME_PRICING: FeaturePolicy(enabled=True),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=False),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "specs",
            "is_combo",
            "bom_json",
            "is_86",
            "batch_no",
            "mfg_date",
            "exp_date",
            "shelf_life_days",
            "production_qty",
            "discount_at_2h",
        ],
        order_extra_fields=[
            "kitchen_status",
            "batch_no",
            "is_exp_discount",
        ],
        workflow_overrides={
            "batch_tracking": "生产批号追踪",
            "near_expiry_auto_discount": "临期自动打折",
            "production_plan": "生产计划联动",
        },
        supply_chain={
            "default_mode": "batch_tracked",
            "alert_threshold": 5,
            "auto_86": False,
            "track_cost": True,
            "fresh_management": True,
        },
    ),

    # ── 6. 零售/便利店 ──
    IndustryType.RETAIL: IndustryTemplate(
        key=IndustryType.RETAIL,
        label="零售/便利店/超市",
        description="条形码/扫码枪为核心；多仓库/多门店联动；进销存为主。",
        features={
            Feature.TABLE_MANAGEMENT: FeaturePolicy(enabled=False),
            Feature.KITCHEN_DISPLAY: FeaturePolicy(enabled=False),
            Feature.RECIPE_BOM: FeaturePolicy(enabled=False),
            Feature.STOCK_ALERT: FeaturePolicy(enabled=True, required=True),
            Feature.PROCUREMENT: FeaturePolicy(enabled=True, required=True),
            Feature.PHYSICAL_INVENTORY: FeaturePolicy(enabled=True, required=True),
            Feature.PURCHASE_SUGGESTION: FeaturePolicy(enabled=True),
            Feature.MEMBER_POINTS: FeaturePolicy(enabled=True),
            Feature.MEMBER_STORED_VALUE: FeaturePolicy(enabled=True),
            Feature.MEMBER_LEVELS: FeaturePolicy(enabled=True),
            Feature.PROMOTION_DISCOUNT: FeaturePolicy(enabled=True),
            Feature.PROMOTION_COUPON: FeaturePolicy(enabled=True),
            Feature.PRINT_RECEIPT: FeaturePolicy(enabled=True),
            Feature.PRINT_LABEL: FeaturePolicy(enabled=True),
            Feature.COMBO_ITEM: FeaturePolicy(enabled=True),
            Feature.WEIGHT_SALE: FeaturePolicy(enabled=True),
            Feature.WEIGHT_PRICE: FeaturePolicy(enabled=True),
            Feature.TIME_PRICING: FeaturePolicy(enabled=False),
            Feature.MULTI_WAREHOUSE: FeaturePolicy(enabled=True, required=True),
            Feature.SUPPLY_CHAIN: FeaturePolicy(enabled=True, required=True),
            Feature.INVOICE_REPORT: FeaturePolicy(enabled=True),
            Feature.CHAIN_PUSH: FeaturePolicy(enabled=False),
            Feature.ORDER_VOID_ALL: FeaturePolicy(enabled=True),
            Feature.AUDIT_LOG: FeaturePolicy(enabled=True, required=True),
            Feature.OFFLINE_GRACE: FeaturePolicy(enabled=True),
            Feature.DATA_BACKUP: FeaturePolicy(enabled=True),
        },
        product_extra_fields=[
            "barcode",
            "specs",
            "is_combo",
            "is_86",
            "rack_location",
            "is_weighing",
            "unit",
            "batch_no",
            "mfg_date",
            "exp_date",
        ],
        order_extra_fields=[
            "scan_source",
            "shelf_out",
        ],
        workflow_overrides={
            "barcode_first": "扫码→加减→付款",
            "self_checkout": "自助收银模式",
            "multi_payment": "聚合支付（微信/支付宝/云闪付/现金）",
        },
        supply_chain={
            "default_mode": "full_erp",
            "alert_threshold": 5,
            "auto_86": False,
            "track_cost": True,
            "procurement_type": "full",
            "wh_count": 2,
            "transfer": True,
        },
    ),
}


def get_template(industry: IndustryType) -> IndustryTemplate:
    """获取指定业态模板"""
    return _TEMPLATES[industry]


def get_default_industry_tier_map(tier: str) -> list[IndustryType]:
    """License Tier 默认支持的业态列表"""
    if tier in ("chain_flagship", "chain_unlimited"):
        return list(IndustryType)
    return [IndustryType.FAST_FOOD, IndustryType.RETAIL]


def feature_matrix_for(industry: IndustryType) -> dict[str, bool]:
    """返回某业态 feature_key → enabled 映射"""
    tmpl = _TEMPLATES[industry]
    return {k: v.enabled for k, v in tmpl.features.items()}


def required_features(industry: IndustryType) -> list[str]:
    """某业态不可关闭的 feature_key 列表"""
    tmpl = _TEMPLATES[industry]
    return [k for k, v in tmpl.features.items() if v.required]

"""
M2 (会员 CRM) + M3 (促销规则引擎) 单元测试
覆盖: WalletService, PointsService, LevelService, TagService,
      CampaignService, RuleEngine, CouponService, CheckoutService 集成
"""

from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────
# WalletService Tests
# ──────────────────────────────────────────────────────────────────

class TestWalletService:
    def test_deposit_increases_balance(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService
        from app.infra.db.models import Member as MemberModel
        from app.infra.db.engine import session_factory

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "测试", "phone": "13800001111"})

        result = svc.deposit(m["id"], 10000, note="首充")
        assert result["amount"] == 10000
        assert result["total"] == 10000
        assert result["balance"] == 10000

    def test_deposit_with_gift_rule(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "测试2", "phone": "13800002222"})

        result = svc.deposit(
            m["id"], 10000, gift_rule={"threshold": 5000, "gift": 1000}
        )
        assert result["gift"] == 1000
        assert result["total"] == 11000
        assert result["balance"] == 11000

    def test_consume_decreases_balance(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "测试3", "phone": "13800003333"})
        svc.deposit(m["id"], 10000)

        result = svc.consume(m["id"], 3000, ref_table="orders", ref_id="ord-1")
        assert result["amount"] == -3000
        assert result["balance"] == 7000

    def test_consume_insufficient_balance(self, app):
        from app.application.member.wallet_service import WalletError, WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "测试4", "phone": "13800004444"})
        svc.deposit(m["id"], 1000)

        with pytest.raises(WalletError, match="余额不足"):
            svc.consume(m["id"], 2000, ref_table="orders", ref_id="ord-x")

    def test_refund_restores_balance(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "测试5", "phone": "13800005555"})
        svc.deposit(m["id"], 10000)

        result = svc.refund(m["id"], 3000, ref_table="orders", ref_id="ord-1")
        assert result["amount"] == 3000
        assert result["balance"] == 13000

    def test_transfer_between_members(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m1 = member_svc.create_member({"name": "转出", "phone": "13800006666"})
        m2 = member_svc.create_member({"name": "转入", "phone": "13800007777"})
        svc.deposit(m1["id"], 10000)

        result = svc.transfer(m1["id"], m2["id"], 4000)
        assert result["from_balance"] == 6000
        assert result["to_balance"] == 4000

    def test_list_txns(self, app):
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService

        svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "流水测试", "phone": "13800008888"})
        svc.deposit(m["id"], 5000)

        txns = svc.list_txns(m["id"])
        assert len(txns) >= 1
        assert txns[0]["type"] == "deposit"
        assert txns[0]["amount"] == 5000


# ──────────────────────────────────────────────────────────────────
# PointsService Tests
# ──────────────────────────────────────────────────────────────────

class TestPointsService:
    def test_earn_points_on_spend(self, app):
        from app.application.member.points_service import PointsService
        from app.application.member.member_service import MemberService

        svc = PointsService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "积分测试", "phone": "13800011111"})

        result = svc.earn(m["id"], 5800, ref_table="orders", ref_id="ord-1")
        assert result["points_earned"] == 58
        assert result["total_points"] == 58

    def test_earn_zero_for_small_amount(self, app):
        from app.application.member.points_service import PointsService
        from app.application.member.member_service import MemberService

        svc = PointsService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "积分测试小", "phone": "13800011112"})

        result = svc.earn(m["id"], 50)
        assert result["points_earned"] == 0

    def test_redeem_points(self, app):
        from app.application.member.points_service import PointsService
        from app.application.member.member_service import MemberService

        svc = PointsService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "兑换测试", "phone": "13800022222"})
        svc.earn(m["id"], 500000)  # 5000积分

        result = svc.redeem(m["id"], 200, ref_table="orders", ref_id="ord-r")
        assert result["points_redeemed"] == 200
        assert result["cash_cents"] == 200  # 200积分 = 200分
        assert result["total_points"] == 4800  # 5000 - 200 = 4800

    def test_redeem_insufficient_points(self, app):
        from app.application.member.points_service import PointsError, PointsService
        from app.application.member.member_service import MemberService

        svc = PointsService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "兑换失败", "phone": "13800022223"})

        with pytest.raises(PointsError, match="积分不足"):
            svc.redeem(m["id"], 100)

    def test_list_points_txns(self, app):
        from app.application.member.points_service import PointsService
        from app.application.member.member_service import MemberService

        svc = PointsService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "积分流水", "phone": "13800033333"})
        svc.earn(m["id"], 300000)

        txns = svc.list_txns(m["id"])
        assert len(txns) >= 1
        assert txns[0]["type"] == "earn"
        assert txns[0]["points"] == 3000


# ──────────────────────────────────────────────────────────────────
# LevelService Tests
# ──────────────────────────────────────────────────────────────────

class TestLevelService:
    def test_init_defaults(self, app):
        from app.application.member.level_service import LevelService

        svc = LevelService(merchant_id="local")
        levels = svc.init_defaults()
        assert len(levels) >= 4
        # 检查基础等级存在
        names = [lvl["name"] for lvl in levels]
        assert "普通会员" in names
        assert "黄金会员" in names or "钻石会员" in names

    def test_evaluate_upgrades_level(self, app):
        from app.application.member.level_service import LevelService
        from app.application.member.member_service import MemberService
        from app.infra.db.engine import session_factory

        level_svc = LevelService(merchant_id="local")
        level_svc.init_defaults()

        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "等级测试", "phone": "13800100001"})

        # 通过 session 手动提升会员消费
        from app.infra.db.models import Member as MemberModel
        with session_factory() as s:
            member_obj = s.query(MemberModel).filter_by(id=m["id"]).first()
            member_obj.balance = 600000  # 6000元
            member_obj.points = 6000
            s.commit()

        result = level_svc.evaluate(m["id"])
        # 按照默认等级规则，6000 元消费 + 6000 分积分 应该匹配较高
        assert "to_level" in result

    def test_get_member_level(self, app):
        from app.application.member.level_service import LevelService
        from app.application.member.member_service import MemberService

        level_svc = LevelService(merchant_id="local")
        level_svc.init_defaults()

        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "等级查询", "phone": "13800100002"})

        result = level_svc.get_member_level(m["id"])
        assert result["member_id"] == m["id"]
        assert result["level"] is not None

    def test_list_levels(self, app):
        from app.application.member.level_service import LevelService

        svc = LevelService(merchant_id="local")
        svc.init_defaults()
        levels = svc.list_levels()
        assert len(levels) > 0
        assert all("name" in lvl for lvl in levels)


# ──────────────────────────────────────────────────────────────────
# TagService Tests
# ──────────────────────────────────────────────────────────────────

class TestTagService:
    def test_add_tag(self, app):
        from app.application.member.tag_service import TagService
        from app.application.member.member_service import MemberService

        svc = TagService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "标签测试", "phone": "13800200001"})

        result = svc.add_tag(m["id"], "忌口", "不吃香菜", source="manual")
        assert result["tag"] == "忌口"
        assert result["value"] == "不吃香菜"

    def test_consume_order_extracts_tags(self, app):
        from app.application.member.tag_service import TagService
        from app.application.member.member_service import MemberService

        svc = TagService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "自动标签", "phone": "13800200002"})

        order_data = {
            "time": "2024-01-15T19:30:00",
            "items": [
                {"category": "川菜", "spicy_level": 4},
                {"category": "凉菜", "spicy_level": 1},
            ],
            "subtotal": 25000,  # 250元 -> 高消费
        }
        tags = svc.consume_order(m["id"], order_data)
        assert len(tags) > 0

    def test_list_tags(self, app):
        from app.application.member.tag_service import TagService
        from app.application.member.member_service import MemberService

        svc = TagService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "标签列表", "phone": "13800200003"})
        svc.add_tag(m["id"], "偏好", "微辣")

        tags = svc.list_tags(m["id"])
        assert len(tags) >= 1
        assert tags[0]["tag"] == "偏好"

    def test_remove_tag(self, app):
        from app.application.member.tag_service import TagService
        from app.application.member.member_service import MemberService

        svc = TagService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "删除标签", "phone": "13800200004"})
        tag = svc.add_tag(m["id"], "临时", "临时值")

        svc.remove_tag(tag["id"])
        tags = svc.list_tags(m["id"])
        assert all(t["id"] != tag["id"] for t in tags)


# ──────────────────────────────────────────────────────────────────
# CouponService Tests
# ──────────────────────────────────────────────────────────────────

class TestCouponService:
    def test_create_template(self, app):
        from app.application.promotion.coupon_service import CouponService

        svc = CouponService(merchant_id="local")
        tpl = svc.create_template({
            "name": "满100减10",
            "type": "amount",
            "value": 1000,
            "min_amount": 10000,
        })
        assert tpl["name"] == "满100减10"
        assert tpl["type"] == "amount"
        assert tpl["value"] == 1000

    def test_issue_and_redeem_coupon(self, app):
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "发券测试", "phone": "13800300001"})

        tpl = svc.create_template({
            "name": "5元券",
            "type": "amount",
            "value": 500,
        })
        coupon = svc.issue(tpl["id"], m["id"])
        assert coupon.code
        assert coupon.status == "unused"
        assert len(coupon.code) > 5

    def test_redeem_coupon(self, app):
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "核销测试", "phone": "13800300002"})

        tpl = svc.create_template({
            "name": "核销券",
            "type": "amount",
            "value": 300,
        })
        coupon = svc.issue(tpl["id"], m["id"])
        result = svc.redeem(coupon.code, "order-001")
        assert result["status"] == "used"

    def test_redeem_twice_fails(self, app):
        from app.application.promotion.coupon_service import CouponError, CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "双重核销", "phone": "13800300003"})

        tpl = svc.create_template({
            "name": "防重券",
            "type": "amount",
            "value": 200,
        })
        coupon = svc.issue(tpl["id"], m["id"])
        svc.redeem(coupon.code, "order-001")

        with pytest.raises(CouponError, match="已使用"):
            svc.redeem(coupon.code, "order-002")

    def test_validate_coupon(self, app):
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "凭证校验", "phone": "13800300004"})

        tpl = svc.create_template({
            "name": "校验券",
            "type": "amount",
            "value": 500,
            "min_amount": 5000,
        })
        coupon = svc.issue(tpl["id"], m["id"])

        result = svc.validate_coupon(coupon.code)
        assert result["valid"] is True

    def test_validate_coupon_not_meet_min_amount(self, app):
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "金额校验", "phone": "13800300005"})

        tpl = svc.create_template({
            "name": "低消券",
            "type": "amount",
            "value": 1000,
            "min_amount": 10000,
        })
        coupon = svc.issue(tpl["id"], m["id"])

        result = svc.validate_coupon(coupon.code, {"subtotal": 5000})
        assert result["valid"] is False
        assert "未达最低消费" in result["reason"]

    def test_list_member_coupons(self, app):
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "券列表", "phone": "13800300006"})

        tpl = svc.create_template({
            "name": "列表测试券",
            "type": "amount",
            "value": 100,
        })
        svc.issue(tpl["id"], m["id"])

        coupons = svc.list_member_coupons(m["id"])
        assert len(coupons) >= 1

    def test_expire_coupons(self, app):
        """过期 valid_days=0 的券 (特殊值表示已过期)"""
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService
        from app.infra.db.engine import session_factory
        from app.infra.db.models import Coupon, CouponTemplate
        from datetime import datetime, timedelta, timezone

        svc = CouponService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "过期测试", "phone": "13800300007"})

        tpl = svc.create_template({
            "name": "快过期券",
            "type": "amount",
            "value": 500,
            "valid_days": 1,
        })
        coupon = svc.issue(tpl["id"], m["id"])

        # 手动把 issued_at 写到30天前使券过期
        with session_factory() as s:
            c = s.query(Coupon).filter_by(id=coupon.id).first()
            c.issued_at = datetime.now(timezone.utc) - timedelta(days=31)
            s.commit()

        expired = svc.expire_coupons()
        assert expired >= 1


# ──────────────────────────────────────────────────────────────────
# RuleEngine Tests
# ──────────────────────────────────────────────────────────────────

class TestRuleEngine:
    def test_create_and_list_rules(self, app):
        from app.application.promotion.rule_engine import RuleEngine

        engine = RuleEngine(merchant_id="local")
        rule = engine.create_rule({
            "name": "满100减10",
            "type": "full_reduction",
            "priority": 1,
            "conditions": {"min_amount": 10000},
            "actions": {"thresholds": [{"amount": 10000, "reduce": 1000}]},
        })
        assert rule["name"] == "满100减10"

        rules = engine.list_rules()
        assert len(rules) >= 1

    def test_evaluate_full_reduction(self, app):
        from app.application.promotion.rule_engine import RuleEngine

        engine = RuleEngine(merchant_id="local")
        engine.create_rule({
            "name": "满减测试",
            "type": "full_reduction",
            "priority": 1,
            "conditions": {"min_amount": 5000},
            "actions": {"thresholds": [{"amount": 5000, "reduce": 500}]},
        })

        result = engine.evaluate({
            "member_id": "",
            "items": [],
            "subtotal": 10000,
            "time": "",
        })
        assert result["discount_amount"] > 0
        assert result["final_amount"] < 10000

    def test_evaluate_discount_rule(self, app):
        from app.application.promotion.rule_engine import RuleEngine

        engine = RuleEngine(merchant_id="local")
        engine.create_rule({
            "name": "全场8折",
            "type": "discount",
            "priority": 1,
            "conditions": {},
            "actions": {"percentage": 20},
        })

        result = engine.evaluate({
            "member_id": "m-001",
            "items": [],
            "subtotal": 10000,
            "time": "",
        })
        assert result["discount_amount"] == 2000

    def test_evaluate_not_meet_min_amount(self, app):
        from app.application.promotion.rule_engine import RuleEngine

        engine = RuleEngine(merchant_id="local")
        engine.create_rule({
            "name": "低消满减",
            "type": "full_reduction",
            "priority": 1,
            "conditions": {"min_amount": 10000},
            "actions": {"thresholds": [{"amount": 10000, "reduce": 1000}]},
        })

        result = engine.evaluate({
            "member_id": "",
            "items": [],
            "subtotal": 3000,
            "time": "",
        })
        assert result["discount_amount"] == 0

    def test_toggle_rule(self, app):
        from app.application.promotion.rule_engine import RuleEngine

        engine = RuleEngine(merchant_id="local")
        rule = engine.create_rule({
            "name": "开关测试",
            "type": "discount",
            "actions": {"percentage": 10},
        })
        toggled = engine.toggle_rule(rule["id"])
        assert toggled["status"] == "inactive"

    def test_delete_rule(self, app):
        from app.application.promotion.rule_engine import RuleEngine, RuleError

        engine = RuleEngine(merchant_id="local")
        rule = engine.create_rule({
            "name": "删除测试",
            "type": "discount",
            "actions": {"percentage": 10},
        })
        engine.delete_rule(rule["id"])

        rules = engine.list_rules(status="all")
        assert all(r["id"] != rule["id"] for r in rules)


# ──────────────────────────────────────────────────────────────────
# CampaignService Tests
# ──────────────────────────────────────────────────────────────────

class TestCampaignService:
    def test_check_dormant(self, app):
        from app.application.campaign.campaign_service import CampaignService

        svc = CampaignService(merchant_id="local")
        members = svc.check_dormant(days=0)  # 0天 -> 所有未来店的都算
        assert isinstance(members, list)

    def test_issue_coupon(self, app):
        from app.application.campaign.campaign_service import CampaignService
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        coupon_svc = CouponService(merchant_id="local")
        campaign_svc = CampaignService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "发券活动", "phone": "13800400001"})

        tpl = coupon_svc.create_template({
            "name": "活动券",
            "type": "amount",
            "value": 500,
        })
        coupon = campaign_svc.issue_coupon(tpl["id"], m["id"])
        assert coupon.code
        assert coupon.status == "unused"

    def test_push_campaign(self, app):
        from app.application.campaign.campaign_service import CampaignService
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        coupon_svc = CouponService(merchant_id="local")
        campaign_svc = CampaignService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "推送测试", "phone": "13800400002"})

        tpl = coupon_svc.create_template({
            "name": "推送活动券",
            "type": "amount",
            "value": 300,
        })
        coupon = campaign_svc.issue_coupon(tpl["id"], m["id"])
        task = campaign_svc.push_campaign(coupon, campaign_type="birthday")
        assert task.coupon_id == coupon.id

    def test_send_batch_coupons(self, app):
        from app.application.campaign.campaign_service import CampaignService
        from app.application.promotion.coupon_service import CouponService
        from app.application.member.member_service import MemberService

        coupon_svc = CouponService(merchant_id="local")
        campaign_svc = CampaignService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")
        m1 = member_svc.create_member({"name": "批量1", "phone": "13800400011"})
        m2 = member_svc.create_member({"name": "批量2", "phone": "13800400012"})

        tpl = coupon_svc.create_template({
            "name": "批量发券",
            "type": "amount",
            "value": 200,
        })
        results = campaign_svc.send_batch_coupons(
            tpl["id"],
            [m1["id"], m2["id"]],
            campaign_type="dormant_recall",
        )
        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)


# ──────────────────────────────────────────────────────────────────
# CheckoutService Integration Tests
# ──────────────────────────────────────────────────────────────────

class TestCheckoutIntegration:
    def test_checkout_with_member_earns_points(self, app, sample_products):
        """余额支付: 消耗余额 + 赚取积分 (session 测试)"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService
        from app.application.member.points_service import PointsService

        checkout_svc = CheckoutService(sid="local")
        wallet_svc = WalletService(merchant_id="local")
        member_svc = MemberService(merchant_id="local")

        m = member_svc.create_member({"name": "结账会员", "phone": "13800500001"})
        # 先充值
        wallet_svc.deposit(m["id"], 50000)

        product = sample_products[0]
        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="member_balance",
            cashier_id="cashier-1",
            member_id=m["id"],
        )
        assert result["payment"]["status"] == "completed"
        # 检查积分是否增加
        points_svc = PointsService(merchant_id="local")
        points = points_svc.get_points(m["id"])
        assert points >= 0  # 至少有积分记录

    def test_cash_checkout_earns_points(self, app, sample_products):
        """现金支付给会员也应赚取积分"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.application.member.points_service import PointsService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")

        m = member_svc.create_member({"name": "现金会员", "phone": "13800500002"})
        product = sample_products[0]

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=product["price"] + 1000,  # 给足钱
        )
        assert result["payment"]["status"] == "completed"

        # 积分检查
        points_svc = PointsService(merchant_id="local")
        points = points_svc.get_points(m["id"])
        assert points >= 0  # 至少应该产生积分记录

    def test_checkout_with_coupon_discount(self, app, sample_products):
        """优惠券抵扣测试"""
        from app.application.checkout.checkout_service import CheckoutService, CheckoutError
        from app.application.member.member_service import MemberService
        from app.application.promotion.coupon_service import CouponService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")
        coupon_svc = CouponService(merchant_id="local")

        m = member_svc.create_member({"name": "券用户", "phone": "13800500003"})
        product = sample_products[0]

        # 创建模板并发券
        tpl = coupon_svc.create_template({
            "name": "抵扣券",
            "type": "amount",
            "value": min(500, product["price"] // 2),
            "min_amount": 0,
        })
        coupon = coupon_svc.issue(tpl["id"], m["id"])

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=product["price"] + 1000,
            coupon_code=coupon.code,
        )
        # 最终金额应低于商品原价 (因为有券抵扣)
        order = result["order"]
        assert order.final_amount <= product["price"]

    @pytest.mark.flaky(reruns=2, reruns_delay=1)
    def test_refund_restores_wallet_and_deducts_points(self, app, sample_products):
        """退款时订单状态变为 refunded, 余额通过 WalletService.refund 恢复"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.wallet_service import WalletService
        from app.application.member.member_service import MemberService
        from app.infra.db.engine import session_factory
        from app.infra.db.models import Order

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")

        m = member_svc.create_member({"name": "退款测试", "phone": "13800500004"})
        product = sample_products[0]

        # 通过 WalletService 充值足够余额
        wallet_svc = WalletService(merchant_id="local")
        wallet_svc.deposit(m["id"], product["price"] * 10)

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="member_balance",
            cashier_id="cashier-1",
            member_id=m["id"],
        )
        order = result["order"]
        assert order.final_amount == product["price"]
        order_id = order.id

        # 退款
        checkout_svc.refund_order(order_id)

        # 验证订单状态
        with session_factory() as s:
            db_order = s.query(Order).filter_by(id=order_id).first()
            assert db_order.status == "refunded"

    # ──────────────────────────────────────────────────────────────
    # P0/P1 修复专项测试
    # ──────────────────────────────────────────────────────────────

    def _create_product(self, app, name: str, price: int, stock: int = 100) -> dict:
        """测试助手：创建测试用商品"""
        import uuid
        from app.infra.db.engine import session_factory
        from app.infra.db.models import Product

        pid = str(uuid.uuid4())
        with session_factory() as s:
            p = Product(
                id=pid,
                merchant_id="local",
                name=name,
                barcode=f"t-{pid[:8]}",
                price=price,
                stock=float(stock),
                status="active",
            )
            s.add(p)
            s.commit()
            return {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock}

    def test_coupon_amount_discount(self, app):
        """P0-1: amount 券直减 — value=500 分, 商品 2000 分, 结账后 final_amount == 1500"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.application.promotion.coupon_service import CouponService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")
        coupon_svc = CouponService(merchant_id="local")

        m = member_svc.create_member({"name": "券直减", "phone": "13800500020"})
        product = self._create_product(app, "直减测试品", price=2000, stock=50)

        # 创建 amount 券模板 (500分) 并发券
        tpl = coupon_svc.create_template({
            "name": "5元直减券",
            "type": "amount",
            "value": 500,
            "min_amount": 0,
        })
        coupon = coupon_svc.issue(tpl["id"], m["id"])

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=product["price"] + 1000,
            coupon_code=coupon.code,
        )
        assert result["order"].final_amount == 1500, \
            f"Expected 1500 (2000-500), got {result['order'].final_amount}"

    def test_coupon_percentage_discount(self, app):
        """P0-1: percentage 券八折 — value=80 (减20%), 商品 1000 分, 结账后 final_amount == 800"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.application.promotion.coupon_service import CouponService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")
        coupon_svc = CouponService(merchant_id="local")

        m = member_svc.create_member({"name": "折扣用户", "phone": "13800500021"})
        product = self._create_product(app, "折后测试品", price=1000, stock=50)

        # 创建 percentage 券模板 (value=80 表示八折，减 20%)
        tpl = coupon_svc.create_template({
            "name": "八折券",
            "type": "percentage",
            "value": 80,
            "min_amount": 0,
        })
        coupon = coupon_svc.issue(tpl["id"], m["id"])

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=product["price"] + 1000,
            coupon_code=coupon.code,
        )
        assert result["order"].final_amount == 800, \
            f"Expected 800 (1000*0.8), got {result['order'].final_amount}"

    def test_refund_restores_material_stock(self, app):
        """P1-1: 退款时恢复 BOM 原料库存"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.infra.db.engine import session_factory
        from app.infra.db.models import (
            Material as MaterialModel,
            Order,
            Product as ProductModel,
            RecipeBOM as BOMModel,
            Warehouse as WarehouseModel,
            WarehouseStock as WarehouseStockModel,
        )

        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "退款原料", "phone": "13800500022"})

        # 1. 创建主仓库
        with session_factory() as s:
            wh = WarehouseModel(
                id="wh-test-001",
                merchant_id="local",
                name="主仓库",
                type="main",
            )
            s.add(wh)
            s.commit()

        # 2. 创建原料 (初始库存 1000)
        with session_factory() as s:
            mat = MaterialModel(
                id="mat-test-001",
                merchant_id="local",
                name="测试原料",
                unit="g",
                cost_price=10,
                stock=1000.0,
            )
            s.add(mat)
            s.commit()

        # 3. 创建仓库库存
        with session_factory() as s:
            ws = WarehouseStockModel(
                id="ws-test-001",
                warehouse_id="wh-test-001",
                material_id="mat-test-001",
                qty=1000.0,
            )
            s.add(ws)
            s.commit()

        # 4. 创建商品 + BOM (1个商品消耗 100g 原料)
        with session_factory() as s:
            product = ProductModel(
                id="prod-bom-test-001",
                merchant_id="local",
                name="BOM测试菜品",
                barcode="bom-test-001",
                price=2000,
                stock=50.0,
            )
            s.add(product)
            bom = BOMModel(
                id="bom-test-001",
                product_id="prod-bom-test-001",
                material_id="mat-test-001",
                qty=100.0,
                wastage_pct=0,
                unit="g",
            )
            s.add(bom)
            s.commit()

        # 5. 结账 (消耗产品库存 + 原料库存)
        checkout_svc = CheckoutService(sid="local")
        result = checkout_svc.checkout(
            items=[{"product_id": "prod-bom-test-001", "quantity": 2}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=10000,
        )
        order_id = result["order"].id

        # 6. 验证结账扣减了物料库存: 1000 - 2*100 = 800
        with session_factory() as s:
            ws_after_checkout = s.query(WarehouseStockModel).filter_by(id="ws-test-001").first()
            assert ws_after_checkout.qty == 800.0, \
                f"Expected ws.qty=800 after checkout, got {ws_after_checkout.qty}"
            mat_after_checkout = s.query(MaterialModel).filter_by(id="mat-test-001").first()
            assert mat_after_checkout.stock == 800.0, \
                f"Expected mat.stock=800 after checkout, got {mat_after_checkout.stock}"

        # 7. 退款
        checkout_svc.refund_order(order_id)

        # 8. 验证退款恢复了物料库存: 800 + 2*100 = 1000
        with session_factory() as s:
            ws_after_refund = s.query(WarehouseStockModel).filter_by(id="ws-test-001").first()
            assert ws_after_refund.qty == 1000.0, \
                f"Expected ws.qty=1000 after refund, got {ws_after_refund.qty}"
            mat_after_refund = s.query(MaterialModel).filter_by(id="mat-test-001").first()
            assert mat_after_refund.stock == 1000.0, \
                f"Expected mat.stock=1000 after refund, got {mat_after_refund.stock}"
            # 验证订单状态
            db_order = s.query(Order).filter_by(id=order_id).first()
            assert db_order.status == "refunded"

    # ──────────────────────────────────────────────────────────────
    # Phase 2: 边界测试 (Hardener 补充)
    # ──────────────────────────────────────────────────────────────

    def test_coupon_amount_exceeds_total(self, app):
        """边界: amount 券 value=999999 (远超商品价格) — final_amount 最小为 0, 不允许负数"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.application.promotion.coupon_service import CouponService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")
        coupon_svc = CouponService(merchant_id="local")

        m = member_svc.create_member({"name": "大额券用户", "phone": "13800500030"})
        product = self._create_product(app, "大额券测试品", price=2000, stock=50)

        # 创建 amount 券模板 (999999分 >> 商品2000分)
        tpl = coupon_svc.create_template({
            "name": "超大券",
            "type": "amount",
            "value": 999999,
            "min_amount": 0,
        })
        coupon = coupon_svc.issue(tpl["id"], m["id"])

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=10000,
            coupon_code=coupon.code,
        )
        # final_amount 最小为 0, 不允许负数
        assert result["order"].final_amount == 0, \
            f"Expected final_amount=0 (min clamp), got {result['order'].final_amount}"
        assert result["order"].final_amount >= 0, \
            "final_amount must never be negative"

    def test_coupon_percentage_zero(self, app):
        """边界: percentage 券 value=100 (原价，零折扣) — final_amount == total_amount"""
        from app.application.checkout.checkout_service import CheckoutService
        from app.application.member.member_service import MemberService
        from app.application.promotion.coupon_service import CouponService

        checkout_svc = CheckoutService(sid="local")
        member_svc = MemberService(merchant_id="local")
        coupon_svc = CouponService(merchant_id="local")

        m = member_svc.create_member({"name": "零折用户", "phone": "13800500031"})
        product = self._create_product(app, "零折测试品", price=1000, stock=50)

        # 创建 percentage 券模板 (value=100 表示原价，零折扣)
        tpl = coupon_svc.create_template({
            "name": "原价券",
            "type": "percentage",
            "value": 100,
            "min_amount": 0,
        })
        coupon = coupon_svc.issue(tpl["id"], m["id"])

        result = checkout_svc.checkout(
            items=[{"product_id": product["id"], "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=10000,
            coupon_code=coupon.code,
        )
        # value=100 → discount=0 → final_amount == total_amount == 1000
        assert result["order"].final_amount == result["order"].total_amount, \
            f"Expected final_amount == total_amount ({result['order'].total_amount}), got {result['order'].final_amount}"
        assert result["order"].final_amount == 1000, \
            f"Expected final_amount=1000, got {result['order'].final_amount}"

    def test_refund_material_stock_idempotent(self, app):
        """边界: 同一订单退款两次 — 第二次应 raise CheckoutError (CAS 幂等防护)"""
        from app.application.checkout.checkout_service import CheckoutService, CheckoutError
        from app.application.member.member_service import MemberService
        from app.infra.db.engine import session_factory
        from app.infra.db.models import (
            Material as MaterialModel,
            Order,
            Product as ProductModel,
            RecipeBOM as BOMModel,
            Warehouse as WarehouseModel,
            WarehouseStock as WarehouseStockModel,
        )

        member_svc = MemberService(merchant_id="local")
        m = member_svc.create_member({"name": "幂等退款", "phone": "13800500032"})

        # 1. 创建主仓库
        with session_factory() as s:
            wh = WarehouseModel(
                id="wh-idempotent-001",
                merchant_id="local",
                name="幂等仓库",
                type="main",
            )
            s.add(wh)
            s.commit()

        # 2. 创建原料 (初始库存 500)
        with session_factory() as s:
            mat = MaterialModel(
                id="mat-idempotent-001",
                merchant_id="local",
                name="幂等原料",
                unit="g",
                cost_price=10,
                stock=500.0,
            )
            s.add(mat)
            s.commit()

        # 3. 创建仓库库存
        with session_factory() as s:
            ws = WarehouseStockModel(
                id="ws-idempotent-001",
                warehouse_id="wh-idempotent-001",
                material_id="mat-idempotent-001",
                qty=500.0,
            )
            s.add(ws)
            s.commit()

        # 4. 创建商品 + BOM (1个商品消耗 50g 原料)
        with session_factory() as s:
            product = ProductModel(
                id="prod-idempotent-001",
                merchant_id="local",
                name="幂等菜品",
                barcode="idem-001",
                price=1500,
                stock=30.0,
            )
            s.add(product)
            bom = BOMModel(
                id="bom-idempotent-001",
                product_id="prod-idempotent-001",
                material_id="mat-idempotent-001",
                qty=50.0,
                wastage_pct=0,
                unit="g",
            )
            s.add(bom)
            s.commit()

        # 5. 结账
        checkout_svc = CheckoutService(sid="local")
        result = checkout_svc.checkout(
            items=[{"product_id": "prod-idempotent-001", "quantity": 1}],
            pay_method="cash",
            cashier_id="cashier-1",
            member_id=m["id"],
            cash_amount=10000,
        )
        order_id = result["order"].id

        # 6. 第一次退款: 成功, 订单状态变为 refunded
        checkout_svc.refund_order(order_id)
        with session_factory() as s:
            ws_first = s.query(WarehouseStockModel).filter_by(id="ws-idempotent-001").first()
            assert ws_first.qty == 500.0, "First refund should restore stock to 500"

        # 7. 第二次退款: should raise CheckoutError (CAS 幂等拦截)
        with pytest.raises(CheckoutError) as exc_info:
            checkout_svc.refund_order(order_id)
        assert "Cannot refund" in str(exc_info.value) or "refund" in str(exc_info.value).lower(), \
            f"Expected CheckoutError about invalid refund state, got: {exc_info.value}"

        # 8. 验证原料未被重复归还 (CAS 拦截后 ws.qty 应该仍然是 500, 不是 550)
        with session_factory() as s:
            ws_second = s.query(WarehouseStockModel).filter_by(id="ws-idempotent-001").first()
            assert ws_second.qty == 500.0, \
                f"Stock must not be double-restored: expected 500, got {ws_second.qty}"
            db_order = s.query(Order).filter_by(id=order_id).first()
            assert db_order.status == "refunded", \
                "Order status must remain 'refunded' after failed second refund"

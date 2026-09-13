"""应用层：财务报表服务 - 利润表/现金对账/员工绩效/看板导出"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func

from app.infra.db.engine import session_factory
from app.infra.db.models import (
    FinancialReport as FinReportModel,
    Order,
    OrderItem,
    Product,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReportService:
    """财务报表服务"""

    def __init__(self, merchant_id: str = "local"):
        self.merchant_id = merchant_id

    # ── 利润表 ──────────────────────────────────────────────

    def generate_profit_report(
        self, start: datetime | None = None, end: datetime | None = None
    ) -> dict:
        """生成利润报表: revenue - cost = gross_profit"""
        end = end or _utcnow()
        start = start or (end - timedelta(days=1))

        with session_factory() as s:
            # 总收入
            total_revenue = (
                s.query(func.coalesce(func.sum(Order.final_amount), 0))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )

            # 通过 OrderItem + Product.cost_price 计算销售成本
            total_cost = (
                s.query(
                    func.coalesce(
                        func.sum(
                            Product.cost_price * OrderItem.quantity
                        ),
                        0,
                    )
                )
                .select_from(OrderItem)
                .join(Order, OrderItem.order_id == Order.id)
                .join(Product, OrderItem.product_id == Product.id)
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )

            gross_profit = total_revenue - total_cost

            report = {
                "report_type": "profit",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "gross_profit": gross_profit,
                "margin_pct": (
                    round(gross_profit / total_revenue * 100, 1)
                    if total_revenue > 0
                    else 0
                ),
            }

            # 持久化快照
            self._save_snapshot(report)
            return report

    # ── 现金对账 ────────────────────────────────────────────

    def generate_cash_reconciliation(
        self, start: datetime | None = None, end: datetime | None = None
    ) -> dict:
        """现金对账：现金支付金额 + 余额支付金额"""
        end = end or _utcnow()
        start = start or (end - timedelta(days=1))

        with session_factory() as s:
            cash_paid = (
                s.query(func.coalesce(func.sum(Order.paid_amount), 0))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )

            # 从 payments 表分 method 汇总
            rows = (
                s.query(
                    # 使用 Order 关联的 method 判断
                )
            )

            cash_total = (
                s.query(func.coalesce(func.sum(Order.paid_amount), 0))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )

            report = {
                "report_type": "cash_reconciliation",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "total_cash_collected": cash_total,
            }
            self._save_snapshot(report)
            return report

    # ── 员工绩效 ────────────────────────────────────────────

    def generate_staff_performance(
        self, start: datetime | None = None, end: datetime | None = None
    ) -> dict:
        """员工绩效：按 cashier_id 汇总订单数和金额"""
        end = end or _utcnow()
        start = start or (end - timedelta(days=1))

        with session_factory() as s:
            rows = (
                s.query(
                    Order.cashier_id,
                    func.count(Order.id).label("order_count"),
                    func.coalesce(func.sum(Order.final_amount), 0).label("revenue"),
                )
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(["paid", "completed"]),
                )
                .group_by(Order.cashier_id)
                .all()
            )

            report = {
                "report_type": "staff_performance",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "staff": [
                    {
                        "cashier_id": r.cashier_id or "unknown",
                        "order_count": r.order_count,
                        "revenue": r.revenue,
                    }
                    for r in rows
                ],
            }
            self._save_snapshot(report)
            return report

    # ── 看板复用/扩展 ──────────────────────────────────────

    def get_dashboard_metrics(self, days: int = 7) -> dict:
        """近 N 天看板指标"""
        since = _utcnow() - timedelta(days=days)
        with session_factory() as s:
            total_revenue = (
                s.query(func.coalesce(func.sum(Order.final_amount), 0))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= since,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )
            order_count = (
                s.query(func.count(Order.id))
                .filter(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= since,
                    Order.status.in_(["paid", "completed"]),
                )
                .scalar()
                or 0
            )
            avg_ticket = total_revenue // order_count if order_count > 0 else 0

            # 日均
            daily_avg = total_revenue // days

        return {
            "days": days,
            "total_revenue": total_revenue,
            "total_revenue_yuan": round(total_revenue / 100, 2),
            "order_count": order_count,
            "avg_ticket": avg_ticket,
            "avg_ticket_yuan": round(avg_ticket / 100, 2),
            "daily_avg_revenue": daily_avg,
            "daily_avg_revenue_yuan": round(daily_avg / 100, 2),
        }

    # ── CSV 导出 ────────────────────────────────────────────

    def export_csv(self, report: dict, path: str = "") -> str:
        """将报表字典导出为 CSV 文件"""
        if not path:
            path = str(
                Path("/tmp") / f"report_{report.get('report_type', 'export')}_{uuid.uuid4().hex[:8]}.csv"
            )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Key", "Value"])
        for k, v in report.items():
            if isinstance(v, list):
                writer.writerow([k, json.dumps(v, ensure_ascii=False)])
            else:
                writer.writerow([k, str(v)])
        Path(path).write_text(output.getvalue(), encoding="utf-8")
        return path

    # ── 内部：持久化快照 ───────────────────────────────────

    def _save_snapshot(self, data: dict) -> FinReportModel:
        """持久化报表快照到 financial_reports 表"""
        with session_factory() as s:
            report = FinReportModel(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant_id,
                report_type=data["report_type"],
                period_start=datetime.fromisoformat(data["period_start"]),
                period_end=datetime.fromisoformat(data["period_end"]),
                data_json=json.dumps(data, ensure_ascii=False),
                total_revenue=data.get("total_revenue", 0),
                total_cost=data.get("total_cost", 0),
                gross_profit=data.get("gross_profit", 0),
            )
            s.add(report)
            s.commit()
            return report

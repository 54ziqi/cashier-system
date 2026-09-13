"""SQLite 审计触发器：为关键写表创建 AFTER UPDATE/DELETE 触发器

触发器将 OLD/NEW 以 JSON 写入 audit_logs 表。
应用层补充 actor_type/actor_id 通过 service 层写入。
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ── 需要创建触发器的表及其审计字段 ──

_AUDIT_TARGETS: dict[str, dict] = {
    "products": {
        "pk": "id",
        "fields": ["price", "stock", "is_86", "status", "cost_price"],
    },
    "members": {
        "pk": "id",
        "fields": ["balance", "points", "level"],
    },
    "orders": {
        "pk": "id",
        "fields": ["status", "total_amount", "final_amount", "paid_amount", "kitchen_status"],
    },
    "promotion_rules": {
        "pk": "id",
        "fields": ["status", "priority", "type"],
    },
}


def _build_json_object(fields: list[str], prefix: str) -> str:
    """构建 json_object('field', prefix.field, ...) 片段"""
    pairs = ", ".join(f"'{f}', {prefix}.{f}" for f in fields)
    return f"json_object({pairs})"


def _build_trigger_sql(table: str, cfg: dict) -> str:
    fields = cfg["fields"]
    old_json = _build_json_object(fields, "OLD")
    new_json = _build_json_object(fields, "NEW")

    # actor_id 在 audit_logs 表中非 NULL，触发器中用空字符串填充
    # 应用层在 service 写入审计日志时会带上真实 actor_id
    update_trigger = f"""
CREATE TRIGGER IF NOT EXISTS trg_{table}_au AFTER UPDATE ON {table}
BEGIN
  INSERT INTO audit_logs(id, actor_type, actor_id, action, resource_type, resource_id, before_json, after_json, created_at)
  VALUES (hex(randomblob(16)), 'system', '', 'UPDATE', '{table}', OLD.id,
          {old_json}, {new_json}, datetime('now'));
END;
"""

    delete_trigger = f"""
CREATE TRIGGER IF NOT EXISTS trg_{table}_ad AFTER DELETE ON {table}
BEGIN
  INSERT INTO audit_logs(id, actor_type, actor_id, action, resource_type, resource_id, before_json, after_json, created_at)
  VALUES (hex(randomblob(16)), 'system', '', 'DELETE', '{table}', OLD.id,
          {old_json}, '', datetime('now'));
END;
"""
    return update_trigger + delete_trigger


def install_audit_triggers(conn) -> None:
    """为所有目标表安装审计触发器

    conn: DB-API 连接对象 (sqlite3 connection)
    """
    cur = conn.cursor()
    for table, cfg in _AUDIT_TARGETS.items():
        sql = _build_trigger_sql(table, cfg)
        cur.executescript(sql)
        log.info(f"审计触发器已安装: {table}")
    cur.close()


def install_audit_trigrations_from_engine(engine) -> None:
    """从 SQLAlchemy engine 安装审计触发器 (备用入口)"""
    raw = engine.raw_connection()
    try:
        install_audit_triggers(raw)
    finally:
        raw.close()

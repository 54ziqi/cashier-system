"""数据库迁移更新：注册新模型"""

from __future__ import annotations

from sqlalchemy import inspect

from . import models  # noqa: F401  -- 注册所有模型
from .engine import Base, get_engine


def run_migrations() -> list[str]:
    engine = get_engine()
    Base.metadata.create_all(engine)

    # 安装 SQLite 审计触发器 (关键写表 UPDATE/DELETE 自动写入 audit_logs)
    from .triggers import install_audit_trigrations_from_engine

    install_audit_trigrations_from_engine(engine)

    insp = inspect(engine)
    return insp.get_table_names()

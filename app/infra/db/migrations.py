"""幂等建表"""
from __future__ import annotations
from sqlalchemy import inspect

from .engine import Base, get_engine


def run_migrations() -> list[str]:
    engine = get_engine()
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    return insp.get_table_names()

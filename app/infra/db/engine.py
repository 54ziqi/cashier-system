"""SQLite + WAL + 单写队列"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def init_engine(settings: Settings):
    global _engine, _SessionLocal
    if _engine is not None:
        return

    url = f"sqlite:///{settings.db_path}"
    _engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "check_same_thread": False,
            "timeout": settings.db.busy_timeout_ms / 1000,
        },
        future=True,
    )

    cache = settings.db.cache_size_kb
    busy = settings.db.busy_timeout_ms

    @event.listens_for(_engine, "connect")
    def _pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        if settings.db.wal:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute(f"PRAGMA busy_timeout={busy}")
        cur.execute(f"PRAGMA cache_size={cache}")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def get_engine():
    assert _engine is not None, "Engine 未初始化"
    return _engine


def session_factory():
    assert _SessionLocal is not None, "Session 未初始化"
    return _SessionLocal()

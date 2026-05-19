from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args: dict = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=True,
    )

    if settings.database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


SessionLocal: sessionmaker = sessionmaker(expire_on_commit=False, autoflush=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """惰性获取 engine 单例——首次调用时构建并绑定 SessionLocal。"""
    engine = _build_engine()
    SessionLocal.configure(bind=engine)
    return engine


def reset_engine() -> None:
    """
    测试用：dispose 旧 engine 并清缓存，下次 get_engine() 按当前配置重建。
    """
    get_engine().dispose()
    get_engine.cache_clear()


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()  # 确保已初始化
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    from app import models  # noqa: F401  pylint: disable=unused-import
    Base.metadata.create_all(bind=get_engine())


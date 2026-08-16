"""数据库会话与 Alembic 迁移状态检查。"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from coursemate.config import get_settings, normalize_database_url


CURRENT_SCHEMA_REVISION = "20260816_0002"


def make_engine(url: str | None = None):
    database_url = url if url is not None else get_settings().DATABASE_URL
    database_url = normalize_database_url(database_url)
    return create_engine(database_url, pool_pre_ping=True)


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _session_factory


def init_db() -> None:
    """检查数据库已由 Alembic 升级到当前版本。

    业务进程不负责隐式建表；部署前应显式执行 ``uv run alembic upgrade head``。
    """
    engine = get_engine()
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            raise RuntimeError(
                "数据库尚未完成 Alembic 迁移，请先执行：uv run alembic upgrade head"
            )
        revisions = set(
            connection.execute(text("SELECT version_num FROM alembic_version"))
            .scalars()
        )
    if revisions != {CURRENT_SCHEMA_REVISION}:
        raise RuntimeError(
            "数据库迁移版本不匹配，请先执行：uv run alembic upgrade head"
        )


def get_session() -> Session:
    return get_session_factory()()

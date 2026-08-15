"""数据库会话与建表。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from coursemate.config import get_settings
from coursemate.db.models import Base


def _prepare_sqlite_url(url: str) -> str:
    """SQLite 相对路径转换为绝对路径。

    uvicorn/Streamlit 的工作目录可能不同，转绝对路径可避免
    "数据库文件找不到/建到别处"这类经典问题。
    """
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///") :]
        if raw != ":memory:" and not Path(raw).is_absolute():
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{Path(raw).resolve()}"
    return url


def make_engine(url: str | None = None):
    settings = get_settings()
    url = url or settings.DATABASE_URL
    if url.startswith("sqlite"):
        url = _prepare_sqlite_url(url)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


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
    """建表（幂等）：启动时或入库前调用，保证表结构存在。"""
    Base.metadata.create_all(bind=get_engine())


def get_session() -> Session:
    return get_session_factory()()

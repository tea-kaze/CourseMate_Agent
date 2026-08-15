from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_coursemate.db")
os.environ.setdefault("MILVUS_URI", "http://localhost:19530")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("SILICONFLOW_API_KEY", "")


@pytest.fixture()
def fresh_db():
    """每个测试使用独立的内存数据库。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from coursemate.db.models import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session()
    Base.metadata.drop_all(engine)

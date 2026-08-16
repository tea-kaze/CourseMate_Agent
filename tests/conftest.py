from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

def _postgres_url(value: str | None, *, variable: str) -> URL:
    if not value:
        raise ValueError(f"{variable} is required")
    try:
        url = make_url(value)
    except ArgumentError as exc:
        raise ValueError(f"{variable} must be a valid PostgreSQL URL") from exc
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise ValueError(f"{variable} must use PostgreSQL with the psycopg driver")
    if not url.database:
        raise ValueError(f"{variable} must include a database name")
    return url


def validate_test_database_urls(
    development_url: str | None,
    test_url: str | None,
) -> URL:
    development = _postgres_url(development_url, variable="DATABASE_URL")
    test = _postgres_url(test_url, variable="TEST_DATABASE_URL")
    if not test.database.lower().endswith("_test"):
        raise ValueError("TEST_DATABASE_URL database name must end with '_test'")
    if test.database.casefold() == development.database.casefold():
        raise ValueError("TEST_DATABASE_URL must not point to the development database")
    return test


try:
    TEST_DATABASE_URL = validate_test_database_urls(
        os.environ.get("DATABASE_URL"),
        os.environ.get("TEST_DATABASE_URL"),
    )
except ValueError as exc:
    raise pytest.UsageError(str(exc)) from exc

os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ.setdefault("MILVUS_URI", "http://localhost:19530")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("SILICONFLOW_API_KEY", "")


@dataclass(frozen=True)
class PostgresSchema:
    name: str
    url: URL


@pytest.fixture()
def postgres_schema_factory() -> Callable[[], PostgresSchema]:
    admin_engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    created: list[str] = []

    def create_schema() -> PostgresSchema:
        name = f"coursemate_test_{uuid4().hex}"
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{name}"')
        created.append(name)
        schema_url = TEST_DATABASE_URL.update_query_dict(
            {"options": f"-csearch_path={name}"}
        )
        return PostgresSchema(name=name, url=schema_url)

    yield create_schema

    for name in reversed(created):
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
    admin_engine.dispose()


@pytest.fixture()
def postgres_schema(postgres_schema_factory) -> PostgresSchema:
    return postgres_schema_factory()


@pytest.fixture()
def postgres_session_factory(postgres_schema) -> sessionmaker[Session]:
    from coursemate.db.models import Base

    engine = create_engine(
        postgres_schema.url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def fresh_db(postgres_session_factory):
    with postgres_session_factory() as session:
        yield session

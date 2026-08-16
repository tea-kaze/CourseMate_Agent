from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from coursemate.db import session as db_session
from coursemate.db.session import init_db, make_engine


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite://",
        "mysql+pymysql://user:password@localhost/coursemate",
        "postgresql+psycopg2://postgres:postgres@localhost/coursemate",
    ],
)
def test_make_engine_rejects_non_psycopg_postgresql_urls(database_url):
    with pytest.raises(ValueError, match="PostgreSQL"):
        make_engine(database_url)


def test_make_engine_normalizes_bare_postgresql_url_to_psycopg():
    engine = make_engine(
        "postgresql://postgres:postgres@localhost/coursemate"
    )
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_init_db_rejects_database_without_alembic_revision(
    postgres_schema, monkeypatch
):
    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    monkeypatch.setattr(db_session, "get_engine", lambda: engine)

    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            init_db()
    finally:
        engine.dispose()


def test_init_db_rejects_outdated_alembic_revision(postgres_schema, monkeypatch):
    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('outdated')")
        )
    monkeypatch.setattr(db_session, "get_engine", lambda: engine)

    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            init_db()
    finally:
        engine.dispose()


def test_init_db_accepts_head_without_creating_business_tables(
    postgres_schema, monkeypatch
):
    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            text(
                "INSERT INTO alembic_version (version_num) "
                "VALUES ('20260816_0002')"
            )
        )
    monkeypatch.setattr(db_session, "get_engine", lambda: engine)

    try:
        init_db()
        tables = set(
            inspect(engine).get_table_names(schema=postgres_schema.name)
        )
        assert tables == {"alembic_version"}
    finally:
        engine.dispose()

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from conftest import validate_test_database_urls
from coursemate.db.models import Base


def test_test_database_url_accepts_dedicated_postgresql_database():
    url = validate_test_database_urls(
        "postgresql+psycopg://user:password@localhost/langchain_db",
        "postgresql://user:password@localhost/coursemate_test",
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "coursemate_test"


@pytest.mark.parametrize(
    ("development_url", "test_url", "message"),
    [
        (
            "postgresql+psycopg://user:password@localhost/langchain_db",
            None,
            "TEST_DATABASE_URL is required",
        ),
        (
            "postgresql+psycopg://user:password@localhost/langchain_db",
            "sqlite:///test.db",
            "must use PostgreSQL",
        ),
        (
            "postgresql+psycopg://user:password@localhost/langchain_db",
            "postgresql+psycopg://user:password@localhost/staging",
            "must end with '_test'",
        ),
        (
            "postgresql+psycopg://user:password@localhost/coursemate_test",
            "postgresql+psycopg://other:password@localhost/coursemate_test",
            "must not point to the development database",
        ),
        (
            "postgresql+psycopg://user:password@localhost/coursemate_test",
            "postgresql+psycopg://other:password@localhost:5432/coursemate_test",
            "must not point to the development database",
        ),
        (
            "postgresql+psycopg://user:password@localhost/coursemate_test",
            "postgresql+psycopg://other:password@127.0.0.1/coursemate_test",
            "must not point to the development database",
        ),
    ],
)
def test_test_database_url_rejects_unsafe_configuration(
    development_url, test_url, message
):
    with pytest.raises(ValueError, match=message):
        validate_test_database_urls(development_url, test_url)


def test_postgres_schemas_are_isolated_and_leave_public_unchanged(
    postgres_schema_factory,
):
    schema_a = postgres_schema_factory()
    schema_b = postgres_schema_factory()
    engine_a = create_engine(schema_a.url, poolclass=NullPool)
    engine_b = create_engine(schema_b.url, poolclass=NullPool)
    public_engine = create_engine(schema_a.url.set(query={}), poolclass=NullPool)

    try:
        public_before = set(inspect(public_engine).get_table_names(schema="public"))
        Base.metadata.create_all(engine_a)
        with engine_a.begin() as connection:
            connection.execute(text("CREATE TABLE isolated_marker (id INTEGER)"))

        assert "isolated_marker" in inspect(engine_a).get_table_names()
        assert "isolated_marker" not in inspect(engine_b).get_table_names()
        assert set(inspect(public_engine).get_table_names(schema="public")) == public_before
    finally:
        engine_a.dispose()
        engine_b.dispose()
        public_engine.dispose()


def test_postgres_schema_connection_has_no_fallback_schema(postgres_schema):
    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            visible_schemas = connection.execute(
                text("SELECT current_schemas(false)")
            ).scalar_one()
        assert visible_schemas == [postgres_schema.name]
    finally:
        engine.dispose()

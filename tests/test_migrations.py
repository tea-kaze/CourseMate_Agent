from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from coursemate.config import get_settings


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "courses",
    "documents",
    "questions",
    "answer_attempts",
    "chat_sessions",
    "chat_messages",
}


def _url_text(database_url: URL) -> str:
    return database_url.render_as_string(hide_password=False)


def _upgrade(database_url: URL, *, version_schema: str | None = None) -> None:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        _url_text(database_url).replace("%", "%%"),
    )
    if version_schema is not None:
        config.set_main_option("version_table_schema", version_schema)
    command.upgrade(config, "head")


def _assert_current_revision(engine, schema: str) -> None:
    with engine.connect() as connection:
        revision = connection.execute(
            text(f'SELECT version_num FROM "{schema}".alembic_version')
        ).scalar_one()
    assert revision == "20260816_0002"


def test_alembic_cli_uses_application_database_url(
    postgres_schema, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", _url_text(postgres_schema.url))
    get_settings.cache_clear()

    try:
        command.upgrade(Config(ROOT / "alembic.ini"), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    try:
        tables = set(inspect(engine).get_table_names(schema=postgres_schema.name))
        assert EXPECTED_TABLES <= tables
        _assert_current_revision(engine, postgres_schema.name)
    finally:
        engine.dispose()


def test_alembic_upgrades_legacy_documents_to_ready(postgres_schema):
    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    metadata = MetaData(schema=postgres_schema.name)
    courses = Table(
        "courses",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(200), nullable=False),
        Column("description", Text, nullable=False),
        Column("created_at", DateTime, nullable=False),
    )
    documents = Table(
        "documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column(
            "course_id",
            Integer,
            ForeignKey(f"{postgres_schema.name}.courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("filename", String(300), nullable=False),
        Column("file_path", String(500), nullable=False),
        Column("doc_type", String(20), nullable=False),
        Column("chunk_count", Integer, nullable=False),
        Column("created_at", DateTime, nullable=False),
    )
    metadata.create_all(engine)
    created_at = datetime(2026, 8, 16)
    with engine.begin() as connection:
        connection.execute(
            courses.insert().values(
                id=1,
                name="数据库",
                description="",
                created_at=created_at,
            )
        )
        connection.execute(
            documents.insert().values(
                id=1,
                course_id=1,
                filename="chapter.md",
                file_path="/tmp/chapter.md",
                doc_type="md",
                chunk_count=3,
                created_at=created_at,
            )
        )

    _upgrade(postgres_schema.url, version_schema=postgres_schema.name)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns(
            "documents", schema=postgres_schema.name
        )
    }
    reflected_documents = Table(
        "documents",
        MetaData(),
        schema=postgres_schema.name,
        autoload_with=engine,
    )
    with engine.connect() as connection:
        row = connection.execute(
            select(
                reflected_documents.c.status,
                reflected_documents.c.last_error,
            ).where(reflected_documents.c.id == 1)
        ).one()

    assert {"status", "last_error"}.issubset(columns)
    assert row == ("ready", None)
    with engine.connect() as connection:
        migrated_created_at = connection.execute(
            select(reflected_documents.c.created_at).where(
                reflected_documents.c.id == 1
            )
        ).scalar_one()
    assert migrated_created_at == created_at.replace(tzinfo=timezone.utc)
    _assert_current_revision(engine, postgres_schema.name)
    engine.dispose()


def test_alembic_initializes_an_empty_database(postgres_schema):
    _upgrade(postgres_schema.url, version_schema=postgres_schema.name)

    engine = create_engine(postgres_schema.url, poolclass=NullPool)
    try:
        tables = set(inspect(engine).get_table_names(schema=postgres_schema.name))
        assert EXPECTED_TABLES <= tables
        columns = {
            column["name"]
            for column in inspect(engine).get_columns(
                "documents", schema=postgres_schema.name
            )
        }
        assert {"status", "last_error"}.issubset(columns)
        expected_timestamps = {
            ("courses", "created_at"),
            ("documents", "created_at"),
            ("questions", "created_at"),
            ("answer_attempts", "created_at"),
            ("chat_sessions", "created_at"),
            ("chat_sessions", "updated_at"),
            ("chat_messages", "created_at"),
        }
        timestamp_timezones = {
            (table_name, column["name"]): column["type"].timezone
            for table_name, column_name in expected_timestamps
            for column in inspect(engine).get_columns(
                table_name, schema=postgres_schema.name
            )
            if column["name"] == column_name
        }
        assert set(timestamp_timezones) == expected_timestamps
        assert all(timestamp_timezones.values())
        _assert_current_revision(engine, postgres_schema.name)
    finally:
        engine.dispose()


def test_alembic_does_not_inherit_revision_from_fallback_schema(
    postgres_schema_factory,
):
    target = postgres_schema_factory()
    fallback = postgres_schema_factory()
    _upgrade(fallback.url)
    target_url = target.url.update_query_dict(
        {"options": f"-csearch_path={target.name},{fallback.name}"}
    )

    _upgrade(target_url, version_schema=target.name)

    engine = create_engine(target.url, poolclass=NullPool)
    try:
        tables = set(inspect(engine).get_table_names(schema=target.name))
        assert EXPECTED_TABLES <= tables
        _assert_current_revision(engine, target.name)
    finally:
        engine.dispose()

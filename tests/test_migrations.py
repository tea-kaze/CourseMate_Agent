from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from coursemate.config import get_settings


ROOT = Path(__file__).resolve().parents[1]


def _upgrade(database_url: str) -> None:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def test_alembic_cli_uses_application_database_url(tmp_path, monkeypatch):
    db_path = tmp_path / "configured.db"
    url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()

    try:
        command.upgrade(Config(ROOT / "alembic.ini"), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(url)
    assert "documents" in inspect(engine).get_table_names()


def test_alembic_upgrades_legacy_documents_to_ready(tmp_path):
    db_path = tmp_path / "legacy.db"
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE courses ("
                "id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, "
                "description TEXT NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL, "
                "filename VARCHAR(300) NOT NULL, file_path VARCHAR(500) NOT NULL, "
                "doc_type VARCHAR(20) NOT NULL, chunk_count INTEGER NOT NULL, "
                "created_at DATETIME NOT NULL, "
                "FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO courses VALUES "
                "(1, '数据库', '', '2026-08-16 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO documents VALUES "
                "(1, 1, 'chapter.md', '/tmp/chapter.md', 'md', 3, "
                "'2026-08-16 00:00:00')"
            )
        )

    _upgrade(url)

    columns = {column["name"] for column in inspect(engine).get_columns("documents")}
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, last_error FROM documents WHERE id = 1")
        ).one()
    assert {"status", "last_error"}.issubset(columns)
    assert row == ("ready", None)


def test_alembic_initializes_an_empty_database(tmp_path):
    db_path = tmp_path / "fresh.db"
    url = f"sqlite:///{db_path.as_posix()}"

    _upgrade(url)

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "alembic_version",
        "courses",
        "documents",
        "questions",
        "answer_attempts",
        "chat_sessions",
        "chat_messages",
    }.issubset(tables)
    columns = {column["name"] for column in inspect(engine).get_columns("documents")}
    assert {"status", "last_error"}.issubset(columns)

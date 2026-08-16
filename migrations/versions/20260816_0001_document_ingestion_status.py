"""Adopt the existing schema and add document ingestion status.

Revision ID: 20260816_0001
Revises:
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Callable

from alembic import op
import sqlalchemy as sa


revision = "20260816_0001"
down_revision = None
branch_labels = None
depends_on = None


def _schema() -> str | None:
    return getattr(op.get_context(), "version_table_schema", None)


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names(schema=_schema()))


def _create_table_if_missing(name: str, create: Callable[[], None]) -> None:
    if name not in _table_names():
        create()


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
) -> None:
    indexes = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes(
            table_name, schema=_schema()
        )
    }
    if index_name not in indexes:
        op.create_index(
            index_name, table_name, columns, unique=False, schema=_schema()
        )


def _course_reference() -> str:
    schema = _schema()
    return f"{schema}.courses.id" if schema else "courses.id"


def upgrade() -> None:
    _create_table_if_missing(
        "courses",
        lambda: op.create_table(
            "courses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("name"),
            schema=_schema(),
        ),
    )
    _create_table_if_missing(
        "documents",
        lambda: op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(300), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("doc_type", sa.String(20), nullable=False),
            sa.Column("chunk_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["course_id"], [_course_reference()], ondelete="CASCADE"
            ),
            schema=_schema(),
        ),
    )

    document_columns = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_columns(
            "documents", schema=_schema()
        )
    }
    if "status" not in document_columns:
        op.add_column(
            "documents",
            sa.Column("status", sa.String(20), nullable=True),
            schema=_schema(),
        )
        documents = sa.table(
            "documents", sa.column("status", sa.String(20)), schema=_schema()
        )
        op.execute(
            documents.update()
            .where(documents.c.status.is_(None))
            .values(status="ready")
        )
        op.alter_column(
            "documents",
            "status",
            existing_type=sa.String(20),
            nullable=False,
            schema=_schema(),
        )
    if "last_error" not in document_columns:
        op.add_column(
            "documents",
            sa.Column("last_error", sa.Text(), nullable=True),
            schema=_schema(),
        )

    _create_table_if_missing(
        "questions",
        lambda: op.create_table(
            "questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("qtype", sa.String(20), nullable=False),
            sa.Column("topic", sa.String(200), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("options", sa.JSON(), nullable=True),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["course_id"], [_course_reference()], ondelete="CASCADE"
            ),
            schema=_schema(),
        ),
    )
    _create_table_if_missing(
        "answer_attempts",
        lambda: op.create_table(
            "answer_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), nullable=False),
            sa.Column("user_answer", sa.Text(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("feedback", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["question_id"],
                [f"{_schema()}.questions.id" if _schema() else "questions.id"],
                ondelete="CASCADE",
            ),
            schema=_schema(),
        ),
    )
    _create_table_if_missing(
        "chat_sessions",
        lambda: op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["course_id"], [_course_reference()], ondelete="SET NULL"
            ),
            schema=_schema(),
        ),
    )
    _create_table_if_missing(
        "chat_messages",
        lambda: op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["session_id"],
                [
                    f"{_schema()}.chat_sessions.id"
                    if _schema()
                    else "chat_sessions.id"
                ],
                ondelete="CASCADE",
            ),
            schema=_schema(),
        ),
    )

    _create_index_if_missing("courses", "ix_courses_name", ["name"])
    _create_index_if_missing("documents", "ix_documents_course_id", ["course_id"])
    _create_index_if_missing("documents", "ix_documents_status", ["status"])
    _create_index_if_missing("questions", "ix_questions_course_id", ["course_id"])
    _create_index_if_missing(
        "answer_attempts", "ix_answer_attempts_question_id", ["question_id"]
    )
    _create_index_if_missing(
        "chat_sessions", "ix_chat_sessions_course_id", ["course_id"]
    )
    _create_index_if_missing(
        "chat_sessions", "ix_chat_sessions_updated_at", ["updated_at"]
    )
    _create_index_if_missing(
        "chat_messages", "ix_chat_messages_session_id", ["session_id"]
    )


def downgrade() -> None:
    indexes = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes(
            "documents", schema=_schema()
        )
    }
    if "ix_documents_status" in indexes:
        op.drop_index(
            "ix_documents_status", table_name="documents", schema=_schema()
        )
    columns = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_columns(
            "documents", schema=_schema()
        )
    }
    if "last_error" in columns:
        op.drop_column("documents", "last_error", schema=_schema())
    if "status" in columns:
        op.drop_column("documents", "status", schema=_schema())

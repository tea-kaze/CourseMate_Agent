"""Store application timestamps with timezone information.

Revision ID: 20260816_0002
Revises: 20260816_0001
Create Date: 2026-08-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260816_0002"
down_revision = "20260816_0001"
branch_labels = None
depends_on = None


TIMESTAMP_COLUMNS = {
    "courses": ("created_at",),
    "documents": ("created_at",),
    "questions": ("created_at",),
    "answer_attempts": ("created_at",),
    "chat_sessions": ("created_at", "updated_at"),
    "chat_messages": ("created_at",),
}


def _schema() -> str | None:
    return getattr(op.get_context(), "version_table_schema", None)


def upgrade() -> None:
    for table_name, column_names in TIMESTAMP_COLUMNS.items():
        for column_name in column_names:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=False),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
                schema=_schema(),
            )


def downgrade() -> None:
    for table_name, column_names in TIMESTAMP_COLUMNS.items():
        for column_name in column_names:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(timezone=False),
                existing_nullable=False,
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
                schema=_schema(),
            )

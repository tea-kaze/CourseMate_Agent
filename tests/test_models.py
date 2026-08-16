from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coursemate.db.models import (
    AnswerAttempt,
    ChatMessage,
    ChatSession,
    Course,
    Document,
    Question,
    utc_isoformat,
)
from coursemate.db.session import CURRENT_SCHEMA_REVISION


@pytest.mark.parametrize(
    ("model", "column_name"),
    [
        (Course, "created_at"),
        (Document, "created_at"),
        (Question, "created_at"),
        (AnswerAttempt, "created_at"),
        (ChatSession, "created_at"),
        (ChatSession, "updated_at"),
        (ChatMessage, "created_at"),
    ],
)
def test_timestamp_columns_are_timezone_aware(model, column_name):
    assert model.__table__.c[column_name].type.timezone is True


def test_runtime_requires_timezone_migration_revision():
    assert CURRENT_SCHEMA_REVISION == "20260816_0002"


def test_utc_isoformat_normalizes_non_utc_offset():
    value = datetime(
        2026,
        8,
        16,
        tzinfo=timezone(timedelta(hours=8)),
    )

    assert utc_isoformat(value) == "2026-08-15T16:00:00+00:00"


def test_utc_isoformat_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_isoformat(datetime(2026, 8, 16))

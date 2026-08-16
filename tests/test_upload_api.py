from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from coursemate.app import main


MEBIBYTE = 1024 * 1024


class _FakeUpload:
    filename = "notes.md"

    def __init__(self, *, declared_size: int | None, payload_size: int):
        self.size = declared_size
        self.payload_size = payload_size
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        read_size = self.payload_size if size < 0 else min(size, self.payload_size)
        return b"x" * read_size


def _settings():
    return SimpleNamespace(MAX_UPLOAD_MB=1)


@pytest.mark.asyncio
async def test_upload_at_limit_uses_bounded_read_and_is_accepted(monkeypatch):
    upload = _FakeUpload(declared_size=MEBIBYTE, payload_size=MEBIBYTE)
    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(
        main,
        "ingest_file",
        lambda filename, content, course_name: {"size": len(content)},
    )

    result = await main.upload_document(upload, "数据库")

    assert result == {"size": MEBIBYTE}
    assert upload.read_sizes == [MEBIBYTE + 1]


@pytest.mark.asyncio
async def test_upload_rejects_declared_size_over_limit_before_read(monkeypatch):
    upload = _FakeUpload(declared_size=MEBIBYTE + 1, payload_size=MEBIBYTE + 1)
    ingest_called = False

    def fake_ingest(*args, **kwargs):
        nonlocal ingest_called
        ingest_called = True
        return {}

    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(main, "ingest_file", fake_ingest)

    with pytest.raises(HTTPException) as exc_info:
        await main.upload_document(upload, "数据库")

    assert exc_info.value.status_code == 413
    assert upload.read_sizes == []
    assert ingest_called is False


@pytest.mark.asyncio
async def test_upload_rejects_stream_over_limit_when_size_is_unknown(monkeypatch):
    upload = _FakeUpload(declared_size=None, payload_size=MEBIBYTE + 1)
    ingest_called = False

    def fake_ingest(*args, **kwargs):
        nonlocal ingest_called
        ingest_called = True
        return {}

    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(main, "ingest_file", fake_ingest)

    with pytest.raises(HTTPException) as exc_info:
        await main.upload_document(upload, "数据库")

    assert exc_info.value.status_code == 413
    assert upload.read_sizes == [MEBIBYTE + 1]
    assert ingest_called is False


@pytest.mark.asyncio
async def test_upload_rejects_stream_over_limit_when_declared_size_is_wrong(
    monkeypatch,
):
    upload = _FakeUpload(declared_size=MEBIBYTE, payload_size=MEBIBYTE + 1)
    ingest_called = False

    def fake_ingest(*args, **kwargs):
        nonlocal ingest_called
        ingest_called = True
        return {}

    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(main, "ingest_file", fake_ingest)

    with pytest.raises(HTTPException) as exc_info:
        await main.upload_document(upload, "数据库")

    assert exc_info.value.status_code == 413
    assert upload.read_sizes == [MEBIBYTE + 1]
    assert ingest_called is False

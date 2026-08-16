from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from coursemate.app import ingestion, main
from coursemate.db import repo
from coursemate.db.models import Base, DocumentStatus


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _ready_document(Session, tmp_path):
    source = tmp_path / "chapter.md"
    source.write_text("content", encoding="utf-8")
    with Session() as session:
        course = repo.get_or_create_course(session, "数据库")
        doc = repo.create_document(
            session, course.id, "chapter.md", str(source), "md", 1
        )
        repo.update_document_status(session, doc, DocumentStatus.READY)
        session.commit()
        return doc.id, source


def test_delete_document_file_preserves_file_when_vector_delete_fails(
    monkeypatch, tmp_path
):
    source = tmp_path / "chapter.md"
    source.write_text("content", encoding="utf-8")

    class FailingVectorstore:
        def delete(self, **kwargs):
            raise RuntimeError("milvus unavailable")

    monkeypatch.setattr(ingestion, "get_vectorstore", lambda: FailingVectorstore())

    with pytest.raises(RuntimeError, match="milvus unavailable"):
        ingestion.delete_document_file(7, str(source))

    assert source.exists()


def test_delete_route_marks_failure_and_keeps_metadata(monkeypatch, tmp_path):
    Session = _session_factory()
    document_id, source = _ready_document(Session, tmp_path)
    observed_statuses: list[str] = []
    monkeypatch.setattr(main, "get_session", Session)
    monkeypatch.setattr(ingestion, "get_session", Session)

    def fail_delete(doc_id: int, file_path: str, **kwargs):
        with Session() as session:
            observed_statuses.append(repo.get_document(session, doc_id).status)
        raise RuntimeError("milvus unavailable")

    monkeypatch.setattr(main, "delete_document_file", fail_delete)

    with pytest.raises(HTTPException) as exc_info:
        main.delete_doc(document_id)

    assert exc_info.value.status_code == 503
    with Session() as session:
        row = repo.get_document(session, document_id)
        assert row is not None
        assert row.status == DocumentStatus.DELETE_FAILED
        assert "milvus unavailable" in (row.last_error or "")
    assert observed_statuses == [DocumentStatus.DELETING]
    assert source.exists()


def test_delete_route_retries_delete_failed_document(monkeypatch, tmp_path):
    Session = _session_factory()
    document_id, source = _ready_document(Session, tmp_path)
    with Session() as session:
        row = repo.get_document(session, document_id)
        repo.update_document_status(
            session,
            row,
            DocumentStatus.DELETE_FAILED,
            last_error="file locked",
        )
        session.commit()
    monkeypatch.setattr(main, "get_session", Session)
    monkeypatch.setattr(ingestion, "get_session", Session)

    def successful_retry(doc_id: int, file_path: str, **kwargs):
        Path(file_path).unlink(missing_ok=True)

    monkeypatch.setattr(main, "delete_document_file", successful_retry)

    assert main.delete_doc(document_id) == {"deleted": document_id}
    with Session() as session:
        assert repo.get_document(session, document_id) is None
    assert not source.exists()

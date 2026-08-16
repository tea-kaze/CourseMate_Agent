"""文档入库的校验逻辑测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import select

from coursemate.app import ingestion
from coursemate.app.ingestion import IngestionError, ingest_file, validate_suffix
from coursemate.db.models import Document


def test_validate_suffix_accepts_docx():
    assert validate_suffix("课程资料.docx") == ".docx"


def test_validate_suffix_rejects_legacy_doc_with_hint():
    with pytest.raises(IngestionError, match="另存为 .docx"):
        validate_suffix("旧版文档.doc")


def test_validate_suffix_rejects_unknown_type():
    with pytest.raises(IngestionError, match="不支持的文件类型"):
        validate_suffix("图片.png")


class _FakeVectorstore:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.documents: list[LangChainDocument] = []

    def add_documents(self, documents):
        self.documents.extend(documents[:1])
        if self.error is not None:
            raise self.error
        self.documents.extend(documents[1:])


def _install_ingestion_fakes(
    monkeypatch, tmp_path, *, vectorstore, session_factory
):
    Session = session_factory
    monkeypatch.setattr(
        ingestion,
        "get_settings",
        lambda: SimpleNamespace(UPLOAD_DIR=str(tmp_path / "uploads")),
    )
    monkeypatch.setattr(
        ingestion,
        "load_document",
        lambda path: [LangChainDocument(page_content="原始内容")],
    )
    monkeypatch.setattr(
        ingestion,
        "split_documents",
        lambda docs: [
            LangChainDocument(page_content="片段一"),
            LangChainDocument(page_content="片段二"),
        ],
    )
    monkeypatch.setattr(ingestion, "get_session", Session)
    monkeypatch.setattr(ingestion, "get_vectorstore", lambda: vectorstore)
    return Session


def test_ingest_file_transitions_pending_document_to_ready(
    monkeypatch, tmp_path, postgres_session_factory
):
    vectorstore = _FakeVectorstore()
    Session = _install_ingestion_fakes(
        monkeypatch,
        tmp_path,
        vectorstore=vectorstore,
        session_factory=postgres_session_factory,
    )

    result = ingest_file("chapter.md", b"content", "数据库")

    with Session() as session:
        row = session.scalar(select(Document))
        assert row is not None
        assert row.status == "ready"
        assert row.last_error is None
        assert row.chunk_count == 2
        assert result["document_id"] == row.id
        assert all(doc.metadata["document_id"] == row.id for doc in vectorstore.documents)
        assert all(doc.metadata["course_id"] == row.course_id for doc in vectorstore.documents)
        assert all(doc.metadata["filename"] == "chapter.md" for doc in vectorstore.documents)
        assert (tmp_path / "uploads" / row.file_path.split("\\")[-1]).exists()


def test_ingest_file_compensates_partial_vectors_and_marks_failed(
    monkeypatch, tmp_path, postgres_session_factory
):
    vectorstore = _FakeVectorstore(RuntimeError("embedding failed"))
    Session = _install_ingestion_fakes(
        monkeypatch,
        tmp_path,
        vectorstore=vectorstore,
        session_factory=postgres_session_factory,
    )
    deleted_ids: list[int] = []
    monkeypatch.setattr(
        ingestion,
        "delete_by_document",
        lambda store, document_id, **kwargs: deleted_ids.append(document_id),
        raising=False,
    )

    with pytest.raises(IngestionError, match="embedding failed"):
        ingest_file("chapter.md", b"content", "数据库")

    with Session() as session:
        row = session.scalar(select(Document))
        assert row is not None
        assert row.status == "ingest_failed"
        assert "embedding failed" in (row.last_error or "")
        assert deleted_ids == [row.id]
        assert not list((tmp_path / "uploads").iterdir())


def test_ingest_file_compensates_vectors_when_ready_commit_fails(
    monkeypatch, tmp_path, postgres_session_factory
):
    vectorstore = _FakeVectorstore()
    Session = _install_ingestion_fakes(
        monkeypatch,
        tmp_path,
        vectorstore=vectorstore,
        session_factory=postgres_session_factory,
    )
    deleted_ids: list[int] = []
    monkeypatch.setattr(
        ingestion,
        "delete_by_document",
        lambda store, document_id, **kwargs: deleted_ids.append(document_id),
        raising=False,
    )
    real_factory = ingestion.get_session
    call_count = 0

    @contextmanager
    def sessions_with_failed_ready_commit():
        nonlocal call_count
        call_count += 1
        with real_factory() as session:
            if call_count == 2:
                real_commit = session.commit

                def fail_commit():
                    session.rollback()
                    raise RuntimeError("ready commit failed")

                session.commit = fail_commit
            yield session

    monkeypatch.setattr(ingestion, "get_session", sessions_with_failed_ready_commit)

    with pytest.raises(IngestionError, match="ready commit failed"):
        ingest_file("chapter.md", b"content", "数据库")

    with Session() as session:
        row = session.scalar(select(Document))
        assert row is not None
        assert row.status == "ingest_failed"
        assert "ready commit failed" in (row.last_error or "")
        assert deleted_ids == [row.id]
        assert not list((tmp_path / "uploads").iterdir())


def test_ingest_file_cleans_partial_file_when_initial_write_fails(
    monkeypatch, tmp_path, postgres_session_factory
):
    vectorstore = _FakeVectorstore()
    _install_ingestion_fakes(
        monkeypatch,
        tmp_path,
        vectorstore=vectorstore,
        session_factory=postgres_session_factory,
    )

    def partial_write(path: Path, content: bytes) -> int:
        with path.open("wb") as stream:
            stream.write(content[:1])
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", partial_write)

    with pytest.raises(IngestionError, match="disk full"):
        ingest_file("chapter.md", b"content", "数据库")

    assert not list((tmp_path / "uploads").iterdir())


def test_ingest_file_records_failure_when_upload_cleanup_fails(
    monkeypatch, tmp_path, postgres_session_factory
):
    vectorstore = _FakeVectorstore(RuntimeError("embedding failed"))
    Session = _install_ingestion_fakes(
        monkeypatch,
        tmp_path,
        vectorstore=vectorstore,
        session_factory=postgres_session_factory,
    )

    def fail_unlink(path: Path, *, missing_ok: bool = False) -> None:
        raise PermissionError("file locked")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(IngestionError, match="embedding failed"):
        ingest_file("chapter.md", b"content", "数据库")

    with Session() as session:
        row = session.scalar(select(Document))
        assert row is not None
        assert row.status == "ingest_failed"
        assert "embedding failed" in (row.last_error or "")

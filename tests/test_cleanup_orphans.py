from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from coursemate.db import repo
from coursemate.db.models import Course, utcnow
from scripts import cleanup_orphans


def test_cleanup_candidates_include_only_ready_orphans_and_stale_ingestions(fresh_db):
    course = repo.get_or_create_course(fresh_db, "清理候选")
    ready_with_vectors = repo.create_document(
        fresh_db, course.id, "indexed.md", "/tmp/indexed", "md", 1
    )
    ready_orphan = repo.create_document(
        fresh_db, course.id, "orphan.md", "/tmp/orphan", "md", 1
    )
    stale_pending = repo.create_document(
        fresh_db, course.id, "stale.md", "/tmp/stale", "md", 0
    )
    recent_failed = repo.create_document(
        fresh_db, course.id, "recent.md", "/tmp/recent", "md", 0
    )
    repo.update_document_status(fresh_db, ready_with_vectors, "ready")
    repo.update_document_status(fresh_db, ready_orphan, "ready")
    repo.update_document_status(
        fresh_db, recent_failed, "ingest_failed", last_error="failed"
    )
    stale_pending.created_at = utcnow() - timedelta(hours=25)
    fresh_db.flush()

    selector = getattr(cleanup_orphans, "select_cleanup_documents", None)
    assert selector is not None
    candidates = selector(
        fresh_db,
        milvus_ids={ready_with_vectors.id},
        stale_before=utcnow() - timedelta(hours=24),
    )

    assert {doc.id for doc in candidates} == {ready_orphan.id, stale_pending.id}


def test_milvus_document_ids_reads_every_iterator_batch(monkeypatch):
    class FakeIterator:
        def __init__(self):
            self.batches = [
                [{"document_id": 1}, {"document_id": 2}],
                [{"document_id": 3}],
                [],
            ]
            self.closed = False

        def next(self):
            return self.batches.pop(0)

        def close(self):
            self.closed = True

    iterator = FakeIterator()

    class FakeClient:
        def __init__(self, uri):
            self.uri = uri

        def list_collections(self):
            return ["coursemate_kb"]

        def query(self, **kwargs):
            raise AssertionError("capped query must not be used")

        def query_iterator(self, **kwargs):
            return iterator

    monkeypatch.setattr(cleanup_orphans, "MilvusClient", FakeClient)
    monkeypatch.setattr(
        cleanup_orphans,
        "get_settings",
        lambda: type("Settings", (), {"MILVUS_COLLECTION": "coursemate_kb"})(),
    )
    monkeypatch.setattr(
        cleanup_orphans,
        "_connection_args",
        lambda: {"uri": "fake.db"},
    )

    assert cleanup_orphans._milvus_document_ids() == {1, 2, 3}
    assert iterator.closed is True


def test_cleanup_empty_courses_after_documents_deleted_in_same_session(fresh_db):
    course = repo.get_or_create_course(fresh_db, "待清理课程")
    document = repo.create_document(
        fresh_db, course.id, "chapter.md", "/tmp/chapter.md", "md", 1
    )
    repo.update_document_status(fresh_db, document, "ready")
    course_id = course.id

    # 先加载 relationship，复现 SQLAlchemy identity map 保留已删除子项的情况。
    assert len(course.documents) == 1
    fresh_db.delete(document)

    deleted_ids = cleanup_orphans.delete_empty_courses(fresh_db)
    fresh_db.flush()

    assert deleted_ids == [course_id]
    assert fresh_db.scalar(select(Course).where(Course.id == course_id)) is None

"""清理孤儿数据：无向量的文档 + 空课程。

- 孤儿文档：PostgreSQL 有记录但 Milvus 无向量（曾指向不同实例或向量库被清空）。
- 空课程：没有任何文档的课程（删除文档后残留）。删除空课程会级联删除其题目与作答记录，
  从而让「错题本」不再显示这些已删文档关联的题目。

用法：
    uv run python scripts/cleanup_orphans.py --dry-run   # 只打印将删除什么
    uv run python scripts/cleanup_orphans.py             # 实际删除
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymilvus import MilvusClient  # noqa: E402
from rich.console import Console  # noqa: E402
from sqlalchemy import select  # noqa: E402

from coursemate.app.ingestion import (  # noqa: E402
    DocumentDeletionError,
    delete_document_consistently,
)
from coursemate.config import get_settings  # noqa: E402
from coursemate.db.models import Course, DocumentStatus, Question, utcnow  # noqa: E402
from coursemate.db.repo import (  # noqa: E402
    list_all_courses,
    list_all_documents,
    list_stale_ingestions,
)
from coursemate.db.session import get_session, init_db  # noqa: E402
from coursemate.rag.vectorstore import _connection_args  # noqa: E402


class UnsafeCleanupError(RuntimeError):
    """Milvus 为空时拒绝默认执行破坏性清理。"""


def validate_empty_milvus_cleanup(
    *,
    milvus_ids: set[int],
    has_ready_documents: bool,
    dry_run: bool,
    allow_empty_milvus: bool,
) -> None:
    if (
        not milvus_ids
        and has_ready_documents
        and not dry_run
        and not allow_empty_milvus
    ):
        raise UnsafeCleanupError(
            "Milvus 集合为空，但 PostgreSQL 中仍有 ready 文档；"
            "请先确认连接和向量迁移，或显式传入 --allow-empty-milvus。"
        )


def _milvus_document_ids() -> set[int]:
    """返回 Milvus 中实际存在向量的 document_id 集合。"""
    settings = get_settings()
    client = MilvusClient(**_connection_args())
    if settings.MILVUS_COLLECTION not in client.list_collections():
        return set()
    iterator = client.query_iterator(
        collection_name=settings.MILVUS_COLLECTION,
        batch_size=1000,
        filter="",
        output_fields=["document_id"],
    )
    document_ids: set[int] = set()
    try:
        while True:
            rows = iterator.next()
            if not rows:
                break
            document_ids.update(
                int(row["document_id"])
                for row in rows
                if row.get("document_id") is not None
            )
    finally:
        iterator.close()
    return document_ids


def select_cleanup_documents(session, *, milvus_ids: set[int], stale_before):
    """选择 ready 但无向量的文档，以及超过期限的失败入库记录。"""
    ready_orphans = [
        document
        for document in list_all_documents(session)
        if document.status == DocumentStatus.READY and document.id not in milvus_ids
    ]
    stale_ingestions = list_stale_ingestions(session, before=stale_before)
    by_id = {document.id: document for document in ready_orphans}
    by_id.update({document.id: document for document in stale_ingestions})
    return [by_id[document_id] for document_id in sorted(by_id)]


def delete_empty_courses(session) -> list[int]:
    """用数据库关系判断空课程，避免已加载 relationship 的 identity-map 缓存。"""
    courses = list(
        session.scalars(
            select(Course).where(~Course.documents.any()).order_by(Course.id)
        )
    )
    ids = [course.id for course in courses]
    for course in courses:
        session.expire(course, ["documents", "questions"])
        session.delete(course)
    session.flush()
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="清理孤儿文档与空课程")
    parser.add_argument("--dry-run", action="store_true", help="只打印将删除的内容，不实际删除")
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=24,
        help="pending/ingest_failed 超过多少小时后允许清理（默认 24）",
    )
    parser.add_argument(
        "--allow-empty-milvus",
        action="store_true",
        help="即使 Milvus 为空也执行实际清理（危险，仅在确认向量确实丢失时使用）",
    )
    args = parser.parse_args()

    init_db()
    console = Console()

    milvus_ids = _milvus_document_ids()
    console.print(f"Milvus 中存在的 document_id：{sorted(milvus_ids)}")

    with get_session() as session:
        stale_before = utcnow() - timedelta(hours=max(args.stale_hours, 0))
        all_documents = list_all_documents(session)
        try:
            validate_empty_milvus_cleanup(
                milvus_ids=milvus_ids,
                has_ready_documents=any(
                    document.status == DocumentStatus.READY
                    for document in all_documents
                ),
                dry_run=args.dry_run,
                allow_empty_milvus=args.allow_empty_milvus,
            )
        except UnsafeCleanupError as exc:
            console.print(f"[red]{exc}[/red]")
            raise SystemExit(2) from exc

        orphan_docs = select_cleanup_documents(
            session,
            milvus_ids=milvus_ids,
            stale_before=stale_before,
        )
        orphan_doc_ids = {d.id for d in orphan_docs}

        # 空课程：无任何文档（删除文档后残留）
        empty_courses = [c for c in list_all_courses(session) if not c.documents]
        # 孤儿课程：有文档但全部无向量
        orphan_courses = [
            c
            for c in list_all_courses(session)
            if c.documents and all(d.id in orphan_doc_ids for d in c.documents)
        ]

        def _q_count(course_id: int) -> int:
            return len(
                session.scalars(
                    select(Question).where(Question.course_id == course_id)
                ).all()
            )

        console.print(f"\n孤儿文档（无向量）{len(orphan_docs)} 个：")
        for d in orphan_docs:
            console.print(f"  - doc {d.id}：{d.filename}（course {d.course_id}）")

        console.print(f"\n空课程（0 文档，删除会级联删题目与作答）{len(empty_courses)} 个：")
        for c in empty_courses:
            console.print(f"  - course {c.id}：{c.name}（{_q_count(c.id)} 题）")

        console.print(f"\n孤儿课程（文档均无向量）{len(orphan_courses)} 个：")
        for c in orphan_courses:
            console.print(f"  - course {c.id}：{c.name}（{_q_count(c.id)} 题）")

        total_courses = len(empty_courses) + len(orphan_courses)
        if args.dry_run:
            console.print(
                f"\n[yellow]dry-run：未做任何删除。将删除 {len(orphan_docs)} 个孤儿文档、"
                f"{total_courses} 个课程（含级联的题目与作答）。[/yellow]"
            )
            return

        document_ids = [document.id for document in orphan_docs]

    deletion_errors: list[int] = []
    for document_id in document_ids:
        try:
            delete_document_consistently(
                document_id,
                allow_incomplete=True,
            )
        except DocumentDeletionError:
            deletion_errors.append(document_id)
            console.print(f"[red]删除文档失败，已保留重试状态：{document_id}[/red]")

    with get_session() as session:
        deleted_course_ids = delete_empty_courses(session)
        session.commit()

        console.print(
            f"\n[bold]已删除 {len(document_ids) - len(deletion_errors)} 个孤儿文档、"
            f"{len(deleted_course_ids)} 个课程"
            f"（含级联的题目与作答）。[/bold]"
        )
        if deletion_errors:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

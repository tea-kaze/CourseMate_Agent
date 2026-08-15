"""清理孤儿数据：无向量的文档 + 空课程。

- 孤儿文档：SQLite 有记录但 Milvus 无向量（曾指向不同 Milvus 实例或向量库被清空）。
- 空课程：没有任何文档的课程（删除文档后残留）。删除空课程会级联删除其题目与作答记录，
  从而让「错题本」不再显示这些已删文档关联的题目。

用法：
    uv run python scripts/cleanup_orphans.py --dry-run   # 只打印将删除什么
    uv run python scripts/cleanup_orphans.py             # 实际删除
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymilvus import MilvusClient  # noqa: E402
from rich.console import Console  # noqa: E402
from sqlalchemy import select  # noqa: E402

from coursemate.app.ingestion import delete_document_file  # noqa: E402
from coursemate.config import get_settings  # noqa: E402
from coursemate.db.models import Question  # noqa: E402
from coursemate.db.repo import delete_document, list_courses, list_documents  # noqa: E402
from coursemate.db.session import get_session, init_db  # noqa: E402
from coursemate.rag.vectorstore import _connection_args  # noqa: E402


def _milvus_document_ids() -> set[int]:
    """返回 Milvus 中实际存在向量的 document_id 集合。"""
    settings = get_settings()
    client = MilvusClient(_connection_args()["uri"])
    if settings.MILVUS_COLLECTION not in client.list_collections():
        return set()
    rows = client.query(
        collection_name=settings.MILVUS_COLLECTION,
        filter="",
        output_fields=["document_id"],
        limit=10000,
    )
    return {int(r["document_id"]) for r in rows if r.get("document_id") is not None}


def main() -> None:
    parser = argparse.ArgumentParser(description="清理孤儿文档与空课程")
    parser.add_argument("--dry-run", action="store_true", help="只打印将删除的内容，不实际删除")
    args = parser.parse_args()

    init_db()
    console = Console()

    milvus_ids = _milvus_document_ids()
    console.print(f"Milvus 中存在的 document_id：{sorted(milvus_ids)}")

    with get_session() as session:
        all_docs = list_documents(session)
        orphan_docs = [d for d in all_docs if d.id not in milvus_ids]
        orphan_doc_ids = {d.id for d in orphan_docs}

        # 空课程：无任何文档（删除文档后残留）
        empty_courses = [c for c in list_courses(session) if not c.documents]
        # 孤儿课程：有文档但全部无向量
        orphan_courses = [
            c
            for c in list_courses(session)
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

        for d in orphan_docs:
            delete_document_file(d.id, d.file_path)
            delete_document(session, d)
        session.flush()

        # 删除空课程与孤儿课程（删掉孤儿文档后变空的课程）
        for c in list_courses(session):
            if not c.documents:
                session.delete(c)
        session.commit()

        console.print(
            f"\n[bold]已删除 {len(orphan_docs)} 个孤儿文档、{total_courses} 个课程"
            f"（含级联的题目与作答）。[/bold]"
        )


if __name__ == "__main__":
    main()

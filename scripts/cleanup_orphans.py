"""清理「无向量」的孤儿元数据。

现象：SQLite 里有课程/文档记录，但 Milvus 里没有对应向量（例如曾指向不同
Milvus 实例、或向量库被清空后），导致「资料管理」显示有文档但检索不到。

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

from coursemate.app.ingestion import delete_document_file  # noqa: E402
from coursemate.config import get_settings  # noqa: E402
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
    parser = argparse.ArgumentParser(description="清理无向量的孤儿元数据")
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

        console.print(
            f"\nSQLite 文档 {len(all_docs)} 个，其中孤儿文档（无向量）{len(orphan_docs)} 个："
        )
        for d in orphan_docs:
            console.print(f"  - doc {d.id}：{d.filename}（course {d.course_id}）")

        orphan_courses = [
            c
            for c in list_courses(session)
            if c.documents and all(d.id in orphan_doc_ids for d in c.documents)
        ]
        console.print(f"\n孤儿课程（全部文档均无向量）{len(orphan_courses)} 个：")
        for c in orphan_courses:
            console.print(f"  - course {c.id}：{c.name}")

        if args.dry_run:
            console.print("\n[yellow]dry-run：未做任何删除。去掉 --dry-run 实际执行。[/yellow]")
            return

        for d in orphan_docs:
            delete_document_file(d.id, d.file_path)
            delete_document(session, d)
        session.flush()

        # 删除变空的课程（孤儿课程删光文档后为空）
        for c in list_courses(session):
            if not c.documents:
                session.delete(c)
        session.commit()

        console.print(
            f"\n[bold]已删除 {len(orphan_docs)} 个孤儿文档、{len(orphan_courses)} 个孤儿课程。[/bold]"
        )


if __name__ == "__main__":
    main()

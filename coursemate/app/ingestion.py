"""文档入库服务：保存文件、切分、向量化并登记元数据。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from loguru import logger

from coursemate.config import get_settings
from coursemate.db.repo import create_document, get_or_create_course
from coursemate.db.session import get_session, init_db
from coursemate.rag.loader import DocumentParseError, load_document, split_documents
from coursemate.rag.vectorstore import get_vectorstore


class IngestionError(Exception):
    pass


def ingest_file(filename: str, content: bytes, course_name: str) -> dict:
    """入库单个文档，返回 {document_id, filename, chunk_count, course_id}。

    完整流程：
    1. 校验扩展名并保存原文到 data/uploads（uuid 重命名避免冲突）；
    2. 加载并切分文档，失败（如扫描件 PDF）时清理文件并抛出明确错误；
    3. 业务元数据写 SQLite/PostgreSQL，向量写 Milvus；
    4. 入库成功后在日志中打印 chunk 数量，便于验收。
    任一步失败都会清理已保存的原文，避免留下半成品数据。
    """
    init_db()
    settings = get_settings()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".md", ".markdown", ".txt"}:
        raise IngestionError(f"不支持的文件类型：{suffix or '（无扩展名）'}")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    dest = upload_dir / stored_name
    dest.write_bytes(content)

    try:
        raw_docs = load_document(dest)
        chunks = split_documents(raw_docs)
        if not chunks:
            raise IngestionError("文档切分后没有内容片段，无法入库。")

        with get_session() as session:
            course = get_or_create_course(session, course_name)
            doc = create_document(
                session,
                course_id=course.id,
                filename=filename,
                file_path=str(dest),
                doc_type=suffix.lstrip("."),
                chunk_count=len(chunks),
            )
            session.commit()
            course_id = course.id
            document_id = doc.id

        vectorstore = get_vectorstore()
        for chunk in chunks:
            chunk.metadata.update(
                {
                    "course_id": course_id,
                    "document_id": document_id,
                    "filename": filename,
                    "source": filename,
                }
            )
        vectorstore.add_documents(chunks)

        logger.info(
            "文档入库成功 course={} doc={} chunks={}",
            course_id,
            document_id,
            len(chunks),
        )
        return {
            "document_id": document_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "course_id": course_id,
            "course_name": course_name,
        }
    except DocumentParseError as exc:
        dest.unlink(missing_ok=True)
        raise IngestionError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        logger.exception("文档入库失败: {}", filename)
        raise IngestionError(f"文档入库失败：{exc}") from exc


def delete_document_file(document_id: int, file_path: str) -> None:
    """删除向量与本地文件（数据库记录由调用方删除）。

    删除必须"向量 + 原文 + 元数据"三处一致，否则会出现
    "文档没了但还能被检索到"的脏数据问题。
    """
    from coursemate.rag.vectorstore import delete_by_document

    try:
        delete_by_document(get_vectorstore(), document_id)
    except Exception:  # noqa: BLE001
        logger.warning("删除向量失败 document_id={}", document_id)
    Path(file_path).unlink(missing_ok=True)

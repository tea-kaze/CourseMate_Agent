"""文档入库服务：保存文件、切分、向量化并登记元数据。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from loguru import logger

from coursemate.config import get_settings
from coursemate.db.models import DocumentStatus
from coursemate.db.repo import (
    create_document,
    delete_document,
    get_document,
    get_or_create_course,
    update_document_status,
)
from coursemate.db.session import get_session, init_db
from coursemate.rag.loader import DocumentParseError, load_document, split_documents
from coursemate.rag.vectorstore import delete_by_document, get_vectorstore


class IngestionError(Exception):
    pass


class DocumentNotFoundError(Exception):
    pass


class DocumentStateError(Exception):
    pass


class DocumentDeletionError(Exception):
    pass


def _safe_unlink(path: Path, *, operation: str) -> None:
    """尽力清理文件，但不让清理异常掩盖原始业务错误。"""
    try:
        path.unlink(missing_ok=True)
    except OSError:  # 文件锁定、权限或磁盘错误由日志保留，状态补偿继续执行
        logger.exception("{}清理文件失败 path={}", operation, path)


def validate_suffix(filename: str) -> str:
    """校验上传文件扩展名，返回小写后缀；不支持的类型给出明确错误。"""
    suffix = Path(filename).suffix.lower()
    if suffix == ".doc":
        raise IngestionError("暂不支持旧版 .doc 文件，请先另存为 .docx 后上传。")
    if suffix not in {".pdf", ".md", ".markdown", ".txt", ".docx"}:
        raise IngestionError(f"不支持的文件类型：{suffix or '（无扩展名）'}")
    return suffix


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
    suffix = validate_suffix(filename)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    dest = upload_dir / stored_name

    document_id: int | None = None
    course_id: int | None = None
    vectorstore = None
    try:
        dest.write_bytes(content)

        with get_session() as session:
            course = get_or_create_course(session, course_name)
            doc = create_document(
                session,
                course_id=course.id,
                filename=filename,
                file_path=str(dest),
                doc_type=suffix.lstrip("."),
                chunk_count=0,
                status=DocumentStatus.PENDING,
            )
            document_id = doc.id
            course_id = course.id
            session.commit()

        raw_docs = load_document(dest)
        chunks = split_documents(raw_docs)
        if not chunks:
            raise IngestionError("文档切分后没有内容片段，无法入库。")

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

        with get_session() as session:
            doc = get_document(session, document_id)
            if doc is None:
                raise IngestionError(f"文档元数据不存在：{document_id}")
            update_document_status(
                session,
                doc,
                DocumentStatus.READY,
                chunk_count=len(chunks),
            )
            session.commit()

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
    except Exception as exc:  # noqa: BLE001
        if vectorstore is not None and document_id is not None:
            try:
                delete_by_document(vectorstore, document_id, missing_ok=True)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "入库补偿删除向量失败 document_id={}", document_id
                )
        _safe_unlink(dest, operation="入库补偿")
        if document_id is not None:
            try:
                with get_session() as session:
                    doc = get_document(session, document_id)
                    if doc is not None:
                        update_document_status(
                            session,
                            doc,
                            DocumentStatus.INGEST_FAILED,
                            last_error=str(exc),
                        )
                        session.commit()
            except Exception:  # noqa: BLE001
                logger.exception(
                    "记录入库失败状态时发生异常 document_id={}", document_id
                )
        logger.exception("文档入库失败: {}", filename)
        message = str(exc) if isinstance(exc, DocumentParseError) else f"文档入库失败：{exc}"
        raise IngestionError(message) from exc


def delete_document_file(document_id: int, file_path: str) -> None:
    """删除向量与本地文件（数据库记录由调用方删除）。

    删除必须"向量 + 原文 + 元数据"三处一致，否则会出现
    "文档没了但还能被检索到"的脏数据问题。
    """
    delete_by_document(get_vectorstore(), document_id, missing_ok=True)
    Path(file_path).unlink(missing_ok=True)


def delete_document_consistently(
    document_id: int,
    *,
    resource_deleter=None,
    allow_incomplete: bool = False,
) -> None:
    """按 deleting -> 资源删除 -> 元数据删除执行可重试删除。"""
    with get_session() as session:
        document = get_document(session, document_id)
        if document is None:
            raise DocumentNotFoundError("文档不存在")
        allowed = {
            DocumentStatus.READY,
            DocumentStatus.DELETING,
            DocumentStatus.DELETE_FAILED,
        }
        if allow_incomplete:
            allowed.update(
                {DocumentStatus.PENDING, DocumentStatus.INGEST_FAILED}
            )
        if document.status not in allowed:
            raise DocumentStateError(f"文档状态不允许删除：{document.status}")
        file_path = document.file_path
        update_document_status(session, document, DocumentStatus.DELETING)
        session.commit()

    deleter = resource_deleter or delete_document_file
    try:
        deleter(document_id, file_path)
        with get_session() as session:
            document = get_document(session, document_id)
            if document is not None:
                delete_document(session, document)
                session.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            with get_session() as session:
                document = get_document(session, document_id)
                if document is not None:
                    update_document_status(
                        session,
                        document,
                        DocumentStatus.DELETE_FAILED,
                        last_error=str(exc),
                    )
                    session.commit()
        except Exception:  # noqa: BLE001
            logger.exception(
                "记录删除失败状态时发生异常 document_id={}", document_id
            )
        raise DocumentDeletionError(str(exc)) from exc

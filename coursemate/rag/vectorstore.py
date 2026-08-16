"""远程 Milvus 向量存储封装。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from langchain_milvus import Milvus

from coursemate.config import get_settings
from coursemate.rag.embeddings import get_embeddings


def _connection_args() -> dict[str, Any]:
    """返回 Docker 或托管 Milvus 的连接参数。"""
    settings = get_settings()
    uri = settings.MILVUS_URI.strip()
    try:
        parsed = urlsplit(uri)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ValueError(
            "MILVUS_URI must point to a remote Milvus http(s) endpoint"
        ) from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError(
            "MILVUS_URI must point to a remote Milvus http(s) endpoint"
        )

    args: dict[str, Any] = {"uri": uri}
    if settings.MILVUS_TOKEN:
        args["token"] = settings.MILVUS_TOKEN
    return args


def get_vectorstore(collection_name: str | None = None) -> Milvus:
    """获取 Milvus 向量库实例。

    开启 enable_dynamic_field，让 course_id/document_id 等业务字段
    随向量一起存储，检索时就能按课程过滤。
    """
    settings = get_settings()
    return Milvus(
        embedding_function=get_embeddings(),
        collection_name=collection_name or settings.MILVUS_COLLECTION,
        connection_args=_connection_args(),
        auto_id=True,
        primary_field="pk",
        text_field="text",
        vector_field="vector",
        enable_dynamic_field=True,
    )


def delete_by_document(
    vectorstore: Milvus, document_id: int, *, missing_ok: bool = False
) -> bool:
    """按 document_id 删除该文档对应的全部向量。

    document_id 是开启动态字段后的顶层字段，过滤表达式直接写字段名
    （与 course_id 一致），而不是 metadata["document_id"]——后者匹配不到。
    直接调用公开的 MilvusClient：langchain-milvus 0.4 的包装器会捕获
    MilvusException 并返回 False，无法区分删除失败与幂等重试。底层客户端
    以是否抛出异常表示删除是否成功，匹配 0 行也属于成功。

    missing_ok 保留用于兼容现有调用；删除本身始终是幂等的。
    """
    vectorstore.client.delete(
        collection_name=vectorstore.collection_name,
        filter=f"document_id == {document_id}",
    )
    return True

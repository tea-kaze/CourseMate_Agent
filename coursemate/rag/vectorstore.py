"""Milvus 向量存储封装。

支持两种模式：
- Milvus Lite（默认，本地文件，无需 Docker）
- Milvus Standalone（MILVUS_URI 设为 http://<host>:19530）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_milvus import Milvus

from coursemate.config import get_settings
from coursemate.rag.embeddings import get_embeddings


def _connection_args() -> dict[str, Any]:
    """根据 MILVUS_URI 判断连接模式：

    - http(s):// 开头 → 连接 Docker 版 Milvus（可带 token 鉴权）；
    - 其他 → 本地文件模式（Milvus Lite），无需 Docker。
    这样同一份代码可以在两种部署形态间无缝切换。
    """
    settings = get_settings()
    uri = settings.MILVUS_URI
    if uri.startswith("http://") or uri.startswith("https://"):
        args: dict[str, Any] = {"uri": uri}
        if settings.MILVUS_TOKEN:
            args["token"] = settings.MILVUS_TOKEN
        return args
    # 本地文件：Milvus Lite
    path = Path(uri)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return {"uri": str(path)}


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
    用包装器的 delete(expr=...)：langchain-milvus 0.4 / pymilvus 3 中
    vectorstore.col 是 _MilvusClientCollection，没有 delete 方法，直接调会抛
    AttributeError，导致向量静默残留（文档删了但还能被检索到）。
    """
    deleted = vectorstore.delete(expr=f"document_id == {document_id}")
    if not deleted and not missing_ok:
        raise RuntimeError(f"未删除到向量：document_id == {document_id}")
    return bool(deleted)

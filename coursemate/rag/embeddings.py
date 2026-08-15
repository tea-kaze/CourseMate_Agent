"""Embedding 模型封装（硅基流动 API）。"""

from __future__ import annotations

from langchain_siliconflow import SiliconFlowEmbeddings

from coursemate.config import get_settings


def get_embeddings() -> SiliconFlowEmbeddings:
    """创建硅基流动 Embedding 客户端（默认 bge-m3，1024 维）。

    用 API 而不是本地模型：免去模型下载和 GPU 依赖，接入成本最低；
    需要换模型时只需改配置，不用动代码。
    """
    settings = get_settings()
    return SiliconFlowEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
    )

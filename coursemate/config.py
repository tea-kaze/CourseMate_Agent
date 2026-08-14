"""全局配置：使用 python-dotenv 加载 .env，再读取系统环境变量。"""

from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# 使用 python-dotenv 加载项目根目录的 .env 文件（不存在时静默跳过）。
# 加载后的变量会写入进程环境，后续 BaseSettings 优先读取系统环境变量。
load_dotenv()


class Settings(BaseSettings):
    """CourseMate 运行配置。

    默认使用 SQLite + 本地 Milvus（lite 模式），可切换为 PostgreSQL 与远程 Milvus。
    """

    model_config = SettingsConfigDict(
        extra="ignore"
    )

    # ---- 模型 ----
    LLM_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # ---- Embedding（硅基流动，默认 bge-m3）----
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # ---- 存储 ----
    DATABASE_URL: str = "sqlite:///./data/coursemate.db"
    MILVUS_URI: str = "./data/milvus_lite.db"
    MILVUS_TOKEN: str = ""
    MILVUS_COLLECTION: str = "coursemate_kb"
    UPLOAD_DIR: str = "data/uploads"

    # ---- RAG ----
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    TOP_K: int = 5

    # ---- 课程问答 ----
    CHAT_SUMMARY_THRESHOLD_MESSAGES: int = 20
    CHAT_HISTORY_CHAR_BUDGET: int = 6000
    CHAT_KEEP_RECENT_MESSAGES: int = 10

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()

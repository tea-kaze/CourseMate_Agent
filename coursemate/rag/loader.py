"""文档加载与切分。"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document as LCDocument
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from coursemate.config import get_settings


SUPPORTED_TYPES = {".pdf", ".md", ".markdown", ".txt"}


class DocumentParseError(Exception):
    """文档解析失败（如 PDF 无文本层）。"""


def _load_pdf(path: Path) -> list[LCDocument]:
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError as exc:  # pragma: no cover
        raise DocumentParseError("未安装 PDF 解析依赖（pypdf）") from exc
    loader = PyPDFLoader(str(path))
    return loader.load()


def _load_text(path: Path) -> list[LCDocument]:
    loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


def load_document(path: Path) -> list[LCDocument]:
    """按扩展名加载文档，返回 LangChain Document 列表。

    关键约束：解析后必须提取到非空文本，否则说明是扫描件/图片型 PDF，
    直接抛 DocumentParseError 给出明确提示，而不是带病入库。
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        raise DocumentParseError(f"不支持的文件类型：{suffix}")
    if suffix == ".pdf":
        docs = _load_pdf(path)
    else:
        docs = _load_text(path)
    text = "\n".join(d.page_content for d in docs).strip()
    if not text:
        raise DocumentParseError(
            "文档未提取到文本内容（可能是扫描件 PDF），请上传带文本层的文件。"
        )
    return docs


def split_documents(docs: list[LCDocument]) -> list[LCDocument]:
    """把长文档切成适合向量检索的片段。

    参数来自配置：
    - chunk_size=800 字符：片段足够承载一个完整知识点，又不至于太模糊；
    - chunk_overlap=120 字符：保证跨片段的知识点不被切丢。
    separators 按中文标点（。；）优先断开，避免把句子拦腰截断。
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    )
    return splitter.split_documents(docs)

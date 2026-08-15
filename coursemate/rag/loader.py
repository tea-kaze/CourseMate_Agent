"""文档加载与切分。"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document as LCDocument
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from coursemate.config import get_settings


SUPPORTED_TYPES = {".pdf", ".md", ".markdown", ".txt", ".docx"}


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


def _docx_text(element) -> str:
    """提取元素内全部 w:t 文本节点（含超链接中的文字）。"""
    from docx.oxml.ns import qn

    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def _load_docx(path: Path) -> list[LCDocument]:
    """按文档正文顺序提取段落与表格文本，图片等非文本内容忽略。"""
    try:
        from docx import Document
        from docx.table import Table
    except ImportError as exc:  # pragma: no cover
        raise DocumentParseError("未安装 Word 解析依赖（python-docx）") from exc

    doc = Document(str(path))
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = _docx_text(child).strip()
            if text:
                lines.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            for row in table.rows:
                cells = [
                    _docx_text(cell._tc).strip().replace("\n", " ")
                    for cell in row.cells
                ]
                if any(cells):
                    lines.append(" | ".join(cells))
    return [LCDocument(page_content="\n".join(lines))]


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
    elif suffix == ".docx":
        docs = _load_docx(path)
    else:
        docs = _load_text(path)
    text = "\n".join(d.page_content for d in docs).strip()
    if not text:
        raise DocumentParseError(
            "文档未提取到文本内容（可能是扫描件 PDF 或空文档），请上传带文本层的文件。"
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

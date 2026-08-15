"""文档入库的校验逻辑测试。"""

from __future__ import annotations

import pytest

from coursemate.app.ingestion import IngestionError, validate_suffix


def test_validate_suffix_accepts_docx():
    assert validate_suffix("课程资料.docx") == ".docx"


def test_validate_suffix_rejects_legacy_doc_with_hint():
    with pytest.raises(IngestionError, match="另存为 .docx"):
        validate_suffix("旧版文档.doc")


def test_validate_suffix_rejects_unknown_type():
    with pytest.raises(IngestionError, match="不支持的文件类型"):
        validate_suffix("图片.png")

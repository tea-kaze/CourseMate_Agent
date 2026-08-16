"""向量删除的字段过滤行为测试。

点名要抓住的两个破坏：
1. Milvus 开启动态字段后，document_id 是顶层字段，表达式必须写
   `document_id == X`，而不是 `metadata["document_id"] == X`；
2. langchain-milvus 0.4 / pymilvus 3 中 `vectorstore.col` 是
   `_MilvusClientCollection`，没有 delete 方法，删除要调包装器的
   `vectorstore.delete(expr=...)`，否则向量静默残留。
"""

from __future__ import annotations

import pytest

from coursemate.rag import vectorstore as vs_module


class _FakeVS:
    def __init__(self, result: bool = True):
        self.result = result
        self.expr: str | None = None
        self.ids = None

    def delete(self, ids=None, expr=None, **kwargs):
        self.ids = ids
        self.expr = expr
        return self.result


def test_delete_by_document_uses_top_level_field_expr():
    vs = _FakeVS()
    vs_module.delete_by_document(vs, 42)
    assert vs.expr == "document_id == 42"


def test_delete_by_document_raises_when_no_vectors_deleted():
    vs = _FakeVS(result=False)
    with pytest.raises(RuntimeError):
        vs_module.delete_by_document(vs, 7)


def test_delete_by_document_allows_missing_vectors_for_retry():
    vs = _FakeVS(result=False)
    vs_module.delete_by_document(vs, 7, missing_ok=True)
    assert vs.expr == "document_id == 7"

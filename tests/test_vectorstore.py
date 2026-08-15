"""向量删除的字段过滤行为测试。

点名要抓住的破坏：Milvus 开启动态字段后，document_id 是顶层字段，
过滤表达式必须写 `document_id == X`，而不是 `metadata["document_id"] == X`
（后者不报错但匹配不到任何记录，导致「文档删了但还能被检索到」的脏数据）。
"""

from __future__ import annotations

from coursemate.rag import vectorstore as vs_module


class _FakeCol:
    def __init__(self, delete_raises: bool = False):
        self.delete_raises = delete_raises
        self.deleted: list[str] = []
        self.queried_filter: str | None = None

    def delete(self, expr: str):
        self.deleted.append(expr)
        if self.delete_raises and expr.startswith("document_id"):
            raise RuntimeError("expr not supported")

    def query(self, filter=None, output_fields=None):
        self.queried_filter = filter
        return [{"pk": 1}, {"pk": 2}]


class _FakeVS:
    def __init__(self, col):
        self.col = col


def test_delete_by_document_uses_top_level_field():
    col = _FakeCol()
    vs_module.delete_by_document(_FakeVS(col), 42)
    assert col.deleted == ["document_id == 42"]


def test_delete_by_document_falls_back_to_pk_scan():
    col = _FakeCol(delete_raises=True)
    vs_module.delete_by_document(_FakeVS(col), 7)
    assert col.queried_filter == "document_id == 7"
    assert col.deleted[-1] == "pk in [1, 2]"

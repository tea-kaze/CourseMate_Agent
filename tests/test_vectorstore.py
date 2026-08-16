"""向量删除的字段过滤与异常传播测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_milvus import Milvus
from pymilvus import MilvusException

from coursemate.rag import vectorstore as vs_module


def test_connection_args_passes_remote_uri_and_token(monkeypatch):
    monkeypatch.setattr(
        vs_module,
        "get_settings",
        lambda: SimpleNamespace(
            MILVUS_URI="https://milvus.example.com:19530",
            MILVUS_TOKEN="user:password",
        ),
    )

    assert vs_module._connection_args() == {
        "uri": "https://milvus.example.com:19530",
        "token": "user:password",
    }


def test_connection_args_omits_empty_token(monkeypatch):
    monkeypatch.setattr(
        vs_module,
        "get_settings",
        lambda: SimpleNamespace(
            MILVUS_URI="http://localhost:19530",
            MILVUS_TOKEN="",
        ),
    )

    assert vs_module._connection_args() == {"uri": "http://localhost:19530"}


def test_connection_args_rejects_local_file_path(monkeypatch, tmp_path):
    local_path = tmp_path / "milvus_lite.db"
    monkeypatch.setattr(
        vs_module,
        "get_settings",
        lambda: SimpleNamespace(
            MILVUS_URI=str(local_path),
            MILVUS_TOKEN="",
        ),
    )

    with pytest.raises(ValueError, match="remote Milvus"):
        vs_module._connection_args()

    assert not local_path.exists()


class _FakeClient:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.args = None
        self.kwargs = None

    def delete(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.result


def _vectorstore_with_client(client: _FakeClient) -> Milvus:
    vectorstore = object.__new__(Milvus)
    vectorstore._milvus_client = client
    vectorstore.collection_name = "coursemate_kb"
    return vectorstore


def test_delete_by_document_calls_client_with_top_level_filter():
    client = _FakeClient(result={"delete_count": 1})
    vectorstore = _vectorstore_with_client(client)

    assert vs_module.delete_by_document(vectorstore, 42) is True

    assert client.args == ()
    assert client.kwargs == {
        "collection_name": "coursemate_kb",
        "filter": "document_id == 42",
    }


def test_delete_by_document_treats_zero_matches_as_idempotent_success():
    client = _FakeClient(result={"delete_count": 0})
    vectorstore = _vectorstore_with_client(client)

    assert vs_module.delete_by_document(vectorstore, 7) is True


def test_delete_by_document_propagates_client_error_when_missing_is_allowed():
    error = MilvusException(message="milvus unavailable")
    client = _FakeClient(error=error)
    vectorstore = _vectorstore_with_client(client)

    with pytest.raises(MilvusException, match="milvus unavailable"):
        vs_module.delete_by_document(vectorstore, 7, missing_ok=True)

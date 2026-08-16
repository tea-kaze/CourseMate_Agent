from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from coursemate.rag import vectorstore as vectorstore_module


class _DeterministicEmbeddings(Embeddings):
    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.lower()
        if "database" in lowered:
            return [1.0, 0.0, 0.0, 0.0]
        if "scheduler" in lowered:
            return [0.0, 1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.mark.integration
def test_remote_milvus_write_filter_and_delete(monkeypatch):
    collection = f"coursemate_test_{uuid4().hex}"
    monkeypatch.setattr(
        vectorstore_module,
        "get_embeddings",
        lambda: _DeterministicEmbeddings(),
    )
    store = vectorstore_module.get_vectorstore(collection)

    try:
        store.add_documents(
            [
                Document(
                    page_content="database transaction",
                    metadata={"course_id": 1, "document_id": 101, "source": "db.md"},
                ),
                Document(
                    page_content="database index",
                    metadata={"course_id": 2, "document_id": 202, "source": "other.md"},
                ),
                Document(
                    page_content="scheduler queue",
                    metadata={"course_id": 1, "document_id": 303, "source": "os.md"},
                ),
            ]
        )

        hits = store.similarity_search(
            "database",
            k=5,
            expr="course_id == 1",
        )
        assert hits
        assert {hit.metadata["course_id"] for hit in hits} == {1}

        assert vectorstore_module.delete_by_document(store, 101) is True
        rows = store.client.query(
            collection_name=collection,
            filter="document_id == 101",
            output_fields=["document_id"],
        )
        assert rows == []
    finally:
        if store.client.has_collection(collection_name=collection):
            store.client.drop_collection(collection_name=collection)

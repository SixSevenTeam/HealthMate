"""Tests for VectorStore (mocked Qdrant client)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.database.vector_db import SearchResult, VectorStore


class TestVectorStore:

    @pytest.fixture
    def mock_qdrant(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def store(self, mock_qdrant):
        with patch("rag.database.vector_db.AsyncQdrantClient", return_value=mock_qdrant):
            s = VectorStore(url="http://test:6333")
            s._client = mock_qdrant
            return s

    async def test_create_collection_new(self, store, mock_qdrant):
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections
        await store.create_collection_if_not_exists("test_col", 1024)
        mock_qdrant.create_collection.assert_called_once()

    async def test_create_collection_exists(self, store, mock_qdrant):
        existing = MagicMock()
        existing.name = "test_col"
        mock_collections = MagicMock()
        mock_collections.collections = [existing]
        mock_qdrant.get_collections.return_value = mock_collections
        await store.create_collection_if_not_exists("test_col", 1024)
        mock_qdrant.create_collection.assert_not_called()

    async def test_insert_vectors(self, store, mock_qdrant):
        embeddings = [[0.1] * 4, [0.2] * 4]
        texts = ["text1", "text2"]
        metadata = [{"document_id": "d1"}, {"document_id": "d2"}]
        await store.insert_vectors("col", embeddings, texts, metadata)
        mock_qdrant.upsert.assert_called_once()
        call_kwargs = mock_qdrant.upsert.call_args[1]
        assert call_kwargs["collection_name"] == "col"
        assert len(call_kwargs["points"]) == 2

    async def test_insert_vectors_payload(self, store, mock_qdrant):
        await store.insert_vectors(
            "col",
            [[0.1, 0.2]],
            ["hello"],
            [{"document_id": "d1", "chunk_index": 0}],
        )
        point = mock_qdrant.upsert.call_args[1]["points"][0]
        assert point.payload["text"] == "hello"
        assert point.payload["document_id"] == "d1"

    async def test_search(self, store, mock_qdrant):
        hit = MagicMock()
        hit.id = str(uuid.uuid4())
        hit.score = 0.95
        hit.payload = {
            "text": "found text",
            "document_id": "d1",
            "chunk_index": 0,
        }
        mock_qdrant.search.return_value = [hit]

        results = await store.search("col", [0.1] * 4, top_k=5, score_threshold=0.5)
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].text == "found text"
        assert results[0].document_id == "d1"
        assert results[0].score == 0.95
        assert "text" not in results[0].metadata

    async def test_search_empty(self, store, mock_qdrant):
        mock_qdrant.search.return_value = []
        results = await store.search("col", [0.1] * 4)
        assert results == []

    async def test_search_null_payload(self, store, mock_qdrant):
        hit = MagicMock()
        hit.id = "abc"
        hit.score = 0.8
        hit.payload = None
        mock_qdrant.search.return_value = [hit]

        results = await store.search("col", [0.1] * 4)
        assert len(results) == 1
        assert results[0].text == ""
        assert results[0].document_id == ""

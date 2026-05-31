"""Tests for HybridRetriever."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.retrieval.retriever import HybridRetriever, RetrievedChunk, get_retriever


class TestRetrievedChunk:

    def test_create(self):
        chunk = RetrievedChunk(
            chunk_id="c1", document_id="d1",
            text="hello", score=0.9, metadata={"k": "v"},
        )
        assert chunk.chunk_id == "c1"
        assert chunk.score == 0.9


class TestHybridRetriever:

    @pytest.fixture
    def retriever(self):
        return HybridRetriever(dense_weight=0.7, sparse_weight=0.3)

    async def test_retrieve_calls_dense_search(self, retriever):
        with (
            patch("rag.core.embeddings.get_embedding_service") as mock_emb_fn,
        ):
            mock_emb = AsyncMock()
            mock_emb.embed_text.return_value = [0.1] * 4
            mock_emb_fn.return_value = mock_emb

            retriever._dense_search = AsyncMock(return_value=[
                RetrievedChunk(chunk_id="c1", document_id="d1",
                               text="found", score=0.95, metadata={}),
            ])

            results = await retriever.retrieve("test query", top_k=5)
            assert len(results) == 1
            assert results[0].text == "found"
            mock_emb.embed_text.assert_called_once_with("test query")
            retriever._dense_search.assert_called_once()

    async def test_retrieve_respects_top_k(self, retriever):
        with patch("rag.core.embeddings.get_embedding_service") as mock_emb_fn:
            mock_emb = AsyncMock()
            mock_emb.embed_text.return_value = [0.1] * 4
            mock_emb_fn.return_value = mock_emb

            chunks = [
                RetrievedChunk(chunk_id=f"c{i}", document_id="d1",
                               text=f"t{i}", score=0.9 - i * 0.1, metadata={})
                for i in range(5)
            ]
            retriever._dense_search = AsyncMock(return_value=chunks)

            results = await retriever.retrieve("q", top_k=3)
            assert len(results) == 3

    async def test_dense_search(self, retriever):
        mock_store = AsyncMock()
        mock_result = MagicMock()
        mock_result.chunk_id = "c1"
        mock_result.document_id = "d1"
        mock_result.text = "txt"
        mock_result.score = 0.8
        mock_result.metadata = {"k": "v"}
        mock_store.search.return_value = [mock_result]

        with (
            patch("rag.database.vector_db.get_vector_store",
                  new_callable=AsyncMock, return_value=mock_store),
            patch("rag.core.config.settings") as mock_cfg,
        ):
            mock_cfg.qdrant_collection_name = "col"
            mock_cfg.retrieval_similarity_threshold = 0.5

            results = await retriever._dense_search([0.1] * 4, top_k=5)
            assert len(results) == 1
            assert results[0].chunk_id == "c1"

    async def test_retrieve_empty(self, retriever):
        with patch("rag.core.embeddings.get_embedding_service") as mock_emb_fn:
            mock_emb = AsyncMock()
            mock_emb.embed_text.return_value = [0.1] * 4
            mock_emb_fn.return_value = mock_emb
            retriever._dense_search = AsyncMock(return_value=[])

            results = await retriever.retrieve("no results query")
            assert results == []

    def test_sparse_search_returns_none(self, retriever):
        result = retriever._sparse_search("query", 5)
        assert result is None

    def test_merge_results_returns_none(self, retriever):
        result = retriever._merge_results([], [])
        assert result is None


class TestGetRetriever:

    def test_singleton(self):
        import rag.retrieval.retriever as mod
        mod._retriever = None
        r1 = get_retriever()
        r2 = get_retriever()
        assert r1 is r2
        mod._retriever = None

"""Tests for EmbeddingService (mocked model)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rag.core.embeddings import EmbeddingService


class TestEmbeddingService:

    @pytest.fixture
    def mock_model(self):
        model = MagicMock()
        model.encode.return_value = np.random.rand(1024).astype(np.float32)
        return model

    @pytest.fixture
    def service(self, mock_model):
        svc = EmbeddingService(model_name="test-model", dimension=1024)
        svc._model = mock_model
        return svc

    async def test_embed_text(self, service, mock_model):
        result = await service.embed_text("test text")
        assert isinstance(result, list)
        assert len(result) == 1024
        mock_model.encode.assert_called_once()

    async def test_embed_batch(self, service, mock_model):
        mock_model.encode.return_value = np.random.rand(3, 1024).astype(np.float32)
        results = await service.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(v) == 1024 for v in results)
        mock_model.encode.assert_called_once()

    async def test_embed_text_normalize_flag(self, service, mock_model):
        await service.embed_text("test")
        call_kwargs = mock_model.encode.call_args
        assert call_kwargs[1].get("normalize_embeddings") is True

    def test_load_model_lazy(self):
        with patch("rag.core.embeddings.SentenceTransformer") as mock_st:
            mock_st.return_value = MagicMock()
            svc = EmbeddingService(model_name="test", dimension=1024)
            assert svc._model is None
            svc._load_model()
            assert svc._model is not None
            mock_st.assert_called_once_with("test")

    def test_load_model_cached(self, service, mock_model):
        m1 = service._load_model()
        m2 = service._load_model()
        assert m1 is m2

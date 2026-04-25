"""Интеграционный тест: Document Pipeline.

Полный пайплайн обработки документа:
MinIO (mock) -> ChunkingService (real) -> EmbeddingService (mock) -> VectorStore (mock) -> Kafka (mock)

Проверяем, что реальный ChunkingService корректно режет JSON-дерево
и результат доходит до вставки в VectorStore.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from test.resources import load_json


class TestDocumentPipeline:
    """Полный путь документа: Kafka-событие -> MinIO -> chunk -> embed -> Qdrant -> status."""

    @pytest.fixture
    def sample_tree(self):
        return load_json("stub/common/json_tree.json")

    @pytest.fixture
    def kafka_event(self):
        return load_json("request/document_pipeline/kafka_event.json")

    async def test_full_document_pipeline(self, sample_tree, kafka_event):
        """Kafka-событие -> MinIO download -> chunk -> embed -> Qdrant upsert -> status sent."""
        from rag.application.document_processor import DocumentProcessor

        mock_minio = AsyncMock()
        mock_minio.download_json.return_value = sample_tree

        mock_embed = AsyncMock()
        mock_embed.embed_batch.return_value = [[0.1] * 1024 for _ in range(10)]

        mock_vstore = AsyncMock()
        mock_vstore.insert_vectors.return_value = None

        mock_producer = AsyncMock()
        mock_producer.send_status.return_value = None

        with (
            patch("rag.application.document_processor.MinioClient", return_value=mock_minio),
            patch("rag.application.document_processor.get_embedding_service", return_value=mock_embed),
            patch("rag.application.document_processor.get_vector_store", return_value=mock_vstore),
            patch("rag.application.document_processor.StatusProducer", return_value=mock_producer),
        ):
            processor = DocumentProcessor()
            await processor.process_document(kafka_event)

        # --- Assertions ---
        # 1. MinIO was called to download the JSON
        mock_minio.download_json.assert_called_once()

        # 2. EmbeddingService received chunks
        mock_embed.embed_batch.assert_called_once()
        embedded_texts = mock_embed.embed_batch.call_args[0][0]
        assert len(embedded_texts) >= 3, f"Expected ≥3 chunks, got {len(embedded_texts)}"

        # 3. Chunks contain expected content
        all_text = " ".join(embedded_texts)
        assert "Парацетамол" in all_text
        assert "Головная боль" in all_text
        assert "Противопоказания" in all_text or "чувствительность" in all_text

        # 4. VectorStore received vectors
        mock_vstore.insert_vectors.assert_called_once()

        # 5. Status was sent as "embedded"
        mock_producer.send_status.assert_called()
        status_call = mock_producer.send_status.call_args
        assert status_call[1]["document_id"] == "doc-integration-1"
        assert status_call[1]["status"] == "embedded"

    async def test_pipeline_error_sends_failed_status(self, sample_tree):
        """При ошибке в pipeline статус 'failed' отправляется в Kafka."""
        from rag.application.document_processor import DocumentProcessor

        mock_minio = AsyncMock()
        mock_minio.download_json.side_effect = RuntimeError("MinIO is down")

        mock_producer = AsyncMock()

        with (
            patch("rag.application.document_processor.MinioClient", return_value=mock_minio),
            patch("rag.application.document_processor.StatusProducer", return_value=mock_producer),
        ):
            processor = DocumentProcessor()
            with pytest.raises(RuntimeError, match="MinIO is down"):
                await processor.process_document({
                    "document_id": "doc-fail-1",
                    "s3_url": "s3://bucket/fail.json",
                })

        mock_producer.send_status.assert_called()
        status_call = mock_producer.send_status.call_args
        assert status_call[1]["status"] == "failed"

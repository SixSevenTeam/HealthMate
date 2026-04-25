"""Tests for DocumentProcessor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.application.document_processor import DocumentProcessor


class TestDocumentProcessor:

    @pytest.fixture
    def mock_deps(self):
        with (
            patch("rag.application.document_processor.MinioClient") as mock_minio_cls,
            patch("rag.application.document_processor.get_chunker") as mock_chunker_fn,
            patch("rag.application.document_processor.StatusProducer") as mock_producer_cls,
        ):
            mock_minio = AsyncMock()
            mock_minio_cls.return_value = mock_minio

            mock_chunker = MagicMock()
            mock_chunker_fn.return_value = mock_chunker

            mock_producer = AsyncMock()
            mock_producer_cls.return_value = mock_producer

            yield {
                "minio": mock_minio,
                "chunker": mock_chunker,
                "producer": mock_producer,
            }

    @pytest.fixture
    def processor(self, mock_deps):
        return DocumentProcessor()

    async def test_process_document_success(self, processor, mock_deps):
        from rag.retrieval.chunking import Chunk

        mock_deps["minio"].download_json.return_value = {"content": "test"}

        chunks = [
            Chunk(text="chunk1", metadata={"section_path": ["S1"]}, chunk_index=0),
            Chunk(text="chunk2", metadata={"section_path": ["S2"]}, chunk_index=1),
        ]
        mock_deps["chunker"].chunk_document.return_value = chunks

        with (
            patch("rag.application.document_processor.get_embedding_service") as mock_emb_fn,
            patch("rag.application.document_processor.get_vector_store") as mock_vs_fn,
        ):
            mock_emb = AsyncMock()
            mock_emb.embed_batch.return_value = [[0.1] * 4, [0.2] * 4]
            mock_emb_fn.return_value = mock_emb

            mock_vs = AsyncMock()
            mock_vs_fn.return_value = mock_vs

            event = {
                "document_id": "doc-1",
                "s3_url": "s3://bucket/doc-1.json",
            }
            await processor.process_document(event)

            mock_deps["minio"].download_json.assert_called_once()
            mock_deps["chunker"].chunk_document.assert_called_once()
            mock_emb.embed_batch.assert_called_once()
            mock_vs.insert_vectors.assert_called_once()
            mock_deps["producer"].send_status.assert_called_with(
                document_id="doc-1",
                status="embedded",
                details={"chunks_created": 2, "vectors_stored": 2},
            )

    async def test_process_document_with_result_bucket(self, processor, mock_deps):
        from rag.retrieval.chunking import Chunk

        mock_deps["minio"].download_json.return_value = {"content": "x"}
        mock_deps["chunker"].chunk_document.return_value = [
            Chunk(text="c", metadata={}, chunk_index=0),
        ]

        with (
            patch("rag.application.document_processor.get_embedding_service") as mock_emb_fn,
            patch("rag.application.document_processor.get_vector_store") as mock_vs_fn,
        ):
            mock_emb = AsyncMock()
            mock_emb.embed_batch.return_value = [[0.1] * 4]
            mock_emb_fn.return_value = mock_emb
            mock_vs_fn.return_value = AsyncMock()

            event = {
                "document_id": "doc-2",
                "result_bucket": "my-bucket",
                "result_file": "doc-2.json",
            }
            await processor.process_document(event)

            call_args = mock_deps["minio"].download_json.call_args[0][0]
            assert "my-bucket" in call_args

    async def test_process_document_failure_sends_error(self, processor, mock_deps):
        mock_deps["minio"].download_json.side_effect = RuntimeError("minio down")

        event = {"document_id": "doc-fail", "s3_url": "s3://b/f.json"}

        with pytest.raises(RuntimeError):
            await processor.process_document(event)

        mock_deps["producer"].send_status.assert_called_with(
            document_id="doc-fail",
            status="failed",
            error={"message": "minio down"},
        )

    async def test_ensure_producer_started_once(self, processor, mock_deps):
        from rag.retrieval.chunking import Chunk

        mock_deps["minio"].download_json.return_value = {"content": "x"}
        mock_deps["chunker"].chunk_document.return_value = [
            Chunk(text="c", metadata={}, chunk_index=0),
        ]

        with (
            patch("rag.application.document_processor.get_embedding_service") as mock_emb_fn,
            patch("rag.application.document_processor.get_vector_store") as mock_vs_fn,
        ):
            mock_emb = AsyncMock()
            mock_emb.embed_batch.return_value = [[0.1] * 4]
            mock_emb_fn.return_value = mock_emb
            mock_vs_fn.return_value = AsyncMock()

            event = {"document_id": "d", "s3_url": "s3://b/f"}
            await processor.process_document(event)
            await processor.process_document(event)

            assert mock_deps["producer"].start.call_count == 1

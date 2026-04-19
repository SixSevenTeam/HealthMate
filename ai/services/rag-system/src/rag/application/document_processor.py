from typing import Dict, Any

import structlog

from rag.core.config import settings
from rag.infrastructure.minio.storage import MinioClient
from rag.retrieval.chunking import get_chunker
from rag.core.embeddings import get_embedding_service
from rag.database.vector_db import get_vector_store
from rag.infrastructure.kafka.producer import StatusProducer

logger = structlog.get_logger()

class DocumentProcessor:
    """
     Обрабатывает документы: chunking -> embedding -> vector DB.
    """

    def __init__(self):
        self.minio_client = MinioClient()
        self.chunker = get_chunker()
        self.status_producer = StatusProducer()
        self._producer_started = False

    async def _ensure_producer_started(self):

        if not self._producer_started:
            await self.status_producer.start()
            self._producer_started = True

    async def process_document(self, event: Dict[str, Any]) -> None:
        await self._ensure_producer_started()

        document_id = event["document_id"]
        s3_url = event["s3_url"]

        logger.info("processing_document_started", document_id=document_id)

        try:
            """
            План:
            1. получить json
            2. разбить на чанки
            3. Embeddings (пока через https://huggingface.co/deepvk/USER-bge-m3)
            4. Сохранить в Qdrant
            5. Отправить статус о завершении
            """
            json_data = await self.minio_client.download_json(s3_url)

            chunks = self.chunker.chunk_document(json_data)
            logger.info("chunking_complete", chunk_count=len(chunks))

            embedding_service = get_embedding_service()
            texts = [chunk.text for chunk in chunks]

            embeddings = await embedding_service.embed_batch(texts)
            logger.info("embeddings_generated", count=len(embeddings))

            vector_store = await get_vector_store()
            metadata = [
                {
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata
                }
                for chunk in chunks
            ]
            await vector_store.insert_vectors(embeddings, texts, metadata)
            logger.info("vectors_stored", count=len(embeddings))

            await self.status_producer.send_status(
                document_id=document_id,
                status="embedded",
                details={
                    "chunks_created": len(chunks),
                    "vectors_stored": len(embeddings),
                }
            )

            logger.info("processing_document_complete", document_id=document_id)

        except Exception as e:
            logger.error(
                "processing_document_failed",
                document_id=document_id,
                error=str(e),
            )

            await self.status_producer.send_status(
                document_id=document_id,
                status="failed",
                error={"message": str(e)},
            )

            raise
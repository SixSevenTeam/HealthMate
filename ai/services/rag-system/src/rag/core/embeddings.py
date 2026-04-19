from typing import List

import structlog
logger = structlog.get_logger()

class EmbeddingService:

    def __init__(self):
        logger.info("embedding_service_initialized", status="stub")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Генерирует embeddings для списка текстов."""
        pass

    async def embed_text(self, text: str) -> List[float]:
        """
        Генерирует embedding для одного текста.

        TODO: Реализовать генерацию через sentence-transformers
        """
        logger.warning("embeddings_not_implemented")
        return []

_embedding_service: EmbeddingService | None = None

def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
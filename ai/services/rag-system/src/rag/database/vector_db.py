from typing import List, Any, Dict

import structlog

logger = structlog.get_logger()

class VectorStore:
    def __init__(self):
        logger.info("vector_store_initialized", status="stub")

    async def create_collection_if_not_exists(self):

        """
        TODO: Реализовать создание коллекции в Qdrant
        """
        logger.warning("vector_db_not_implemented")

    async def insert_vectors(
            self,
            embeddings: List[List[float]],
            texts: List[str],
            metadata: List[Dict[str, Any]],
    ):
        logger.warning(
            "vector_db_not_implemented",
            count=len(embeddings) if embeddings else 0
        )



_service: VectorStore | None = None

async def get_vector_store():
    global _service
    if _service is None:
        _service = VectorStore()
        await _service.create_collection_if_not_exists()
    return _service
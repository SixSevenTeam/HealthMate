from typing import List


class EmbeddingService:


    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Генерирует embeddings для списка текстов."""
        pass

_service = None

def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
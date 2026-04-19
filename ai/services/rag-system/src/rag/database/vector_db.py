from typing import List, Any


class VectorStore:
   async def insert_vectors(self, embeddings: List[List[float]], texts: List[str], metadata: list[dict[str, Any]]):
        pass

_service = None

def get_vector_store():
    global _service
    if _service is None:
        _service = VectorStore()
    return _service
from typing import List, Dict, Any
from dataclasses import dataclass

import structlog
from rag.core.config import settings

logger = structlog.get_logger()
@dataclass
class Chunk:
    """Чанк документа."""
    text: str
    metadata: Dict[str, Any]
    chunk_index: int

class ChunkingService:
    def __init__(
            self,
            chunk_size: int = settings.chunk_size,
            chunk_overlap: int = settings.chunk_overlap,
            min_chunk_size: int = settings.min_chunk_size,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    async def chunk_document(self, json_data: Dict[str, Any]) -> List[Chunk]:
        """Генерирует embeddings для списка текстов."""
        pass

_service = None

def get_chunker():
    global _service
    if _service is None:
        _service = ChunkingService()
    return _service
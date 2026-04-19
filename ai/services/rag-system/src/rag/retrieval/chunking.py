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
    async def chunk_document(self, json_data: Dict[str, Any]) -> List[Chunk]:
        """Генерирует embeddings для списка текстов."""
        pass

_service = None

def get_chunker():
    global _service
    if _service is None:
        _service = ChunkingService()
    return _service
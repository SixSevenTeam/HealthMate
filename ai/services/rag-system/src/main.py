"""Entry point для RAG indexer.

Однократный запуск:
- Читает документы из dataset_root
- Разбивает на чанки
- Загружает эмбеддинги в Qdrant
"""

from __future__ import annotations

import asyncio
import structlog

from rag.core.config import settings
from rag.core.logger import setup_logging
from rag.indexer import index_dataset

setup_logging()
logger = structlog.get_logger()


async def main() -> None:
    """Запускает индексирование датасета в Qdrant."""
    logger.info(
        "indexing_service_starting",
        service=settings.service_name,
        version=settings.service_version,
        qdrant_url=settings.qdrant_url,
        dataset_root=settings.dataset_root,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    try:
        await index_dataset()
        logger.info("indexing_completed_successfully")
    except Exception as e:
        logger.error("indexing_failed", error=str(e), exc_info=True)
        raise




if __name__ == "__main__":
    asyncio.run(main())

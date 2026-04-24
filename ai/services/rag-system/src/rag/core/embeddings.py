"""Сервис генерации векторных эмбеддингов.

Использует модель deepvk/USER-bge-m3 через HuggingFace sentence-transformers.
Модель оптимизирована для русского языка медицинской тематики.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger()


class EmbeddingService:
    """Генерирует векторные эмбеддинги через sentence-transformers.

    Синглтон — модель загружается один раз при первом использовании.
    Синхронный вызов модели оборачивается в asyncio.to_thread для
    сохранения асинхронности приложения.
    """

    def __init__(self, model_name: str, dimension: int) -> None:
        """
        Args:
            model_name: Имя модели HuggingFace (напр. deepvk/USER-bge-m3).
            dimension: Размерность вектора (для USER-bge-m3 = 1024).
        """
        self._model_name = model_name
        self._dimension = dimension
        self._model = None  # TODO: загрузить SentenceTransformer(model_name)
        log.info("embedding_service_initialized", model=model_name, dimension=dimension)

    async def embed_text(self, text: str) -> list[float]:
        """Генерирует эмбеддинг для одного текста.

        Args:
            text: Входной текст для эмбеддинга.

        Returns:
            Вектор вещественных чисел длиной self._dimension.
        """
        # TODO: asyncio.to_thread(self._model.encode, text)
        log.warning("embed_text_not_implemented", model=self._model_name)
        pass

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Батчевая генерация эмбеддингов для повышения производительности.

        Args:
            texts: Список текстов.

        Returns:
            Список векторов длиной self._dimension.
        """
        # TODO: asyncio.to_thread(self._model.encode, texts, batch_size=32)
        log.warning("embed_batch_not_implemented", count=len(texts))
        pass


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Возвращает singleton-экземпляр EmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        from rag.core.config import settings
        _embedding_service = EmbeddingService(
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    return _embedding_service

"""Адаптер для векторной базы данных Qdrant.

Qdrant хранит эмбеддинги чанков документов и обеспечивает
семантический (dense) поиск по запросам пользователей.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

log = structlog.get_logger()


@dataclass
class SearchResult:
    """Результат поиска в векторной базе."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore:
    """Клиент Qdrant для хранения и поиска векторных эмбеддингов.

    Коллекция соответствует одному пространству документов платформы HealthMate.
    Каждый вектор — это эмбеддинг одного чанка документа с метаданными
    (document_id, chunk_index, section_path и т.п.).
    """

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        from rag.core.config import settings
        self._client = AsyncQdrantClient(
            url=url or settings.qdrant_url,
            api_key=api_key or settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )
        log.info("vector_store_initialized", url=url or settings.qdrant_url)

    async def create_collection_if_not_exists(
        self, collection: str, dimension: int
    ) -> None:
        """Создаёт коллекцию в Qdrant, если её ещё нет.

        Args:
            collection: Имя коллекции.
            dimension: Размерность векторов (должна совпадать с моделью эмбеддингов).
        """
        collections = await self._client.get_collections()
        existing_names = [c.name for c in collections.collections]

        if collection not in existing_names:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            log.info("qdrant_collection_created", collection=collection, dimension=dimension)
        else:
            log.debug("qdrant_collection_exists", collection=collection)

    async def insert_vectors(
        self,
        collection: str,
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict[str, Any]],
    ) -> None:
        """Сохраняет векторы с текстами и метаданными в Qdrant.

        Args:
            collection: Имя коллекции.
            embeddings: Список векторов.
            texts: Исходные тексты чанков.
            metadata: Метаданные (document_id, chunk_index, section_path).
        """
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={"text": text, **meta},
            )
            for emb, text, meta in zip(embeddings, texts, metadata)
        ]

        await self._client.upsert(
            collection_name=collection,
            points=points,
        )
        log.info("vectors_inserted", collection=collection, count=len(points))

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Семантический поиск ближайших чанков по векторному запросу.

        Args:
            collection: Имя коллекции для поиска.
            query_vector: Вектор запроса пользователя.
            top_k: Максимальное количество результатов.
            score_threshold: Минимальный порог схожести (cosine similarity).

        Returns:
            Список найденных чанков, отсортированных по убыванию релевантности.
        """
        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        search_results = []
        for hit in results:
            payload = hit.payload or {}
            search_results.append(
                SearchResult(
                    chunk_id=str(hit.id),
                    document_id=payload.get("document_id", ""),
                    text=payload.get("text", ""),
                    score=hit.score,
                    metadata={k: v for k, v in payload.items() if k != "text"},
                )
            )

        log.info("search_complete", collection=collection, results=len(search_results))
        return search_results


_vector_store: VectorStore | None = None


async def get_vector_store() -> VectorStore:
    """Возвращает singleton-экземпляр VectorStore."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        from rag.core.config import settings
        await _vector_store.create_collection_if_not_exists(
            collection=settings.qdrant_collection_name,
            dimension=settings.embedding_dimension,
        )
    return _vector_store

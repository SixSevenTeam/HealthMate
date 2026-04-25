"""Гибридный ретривер: плотный (dense) + разреженный (BM25) поиск.

Плотный поиск — косинусная близость векторов эмбеддингов в Qdrant.
Разреженный поиск — BM25 по тексту чанков (rank-bm25).
Результаты объединяются через Reciprocal Rank Fusion (RRF).

Веса по умолчанию: 0.7 dense / 0.3 sparse (настраиваются через Settings).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class RetrievedChunk:
    """Найденный чанк с оценкой релевантности."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class HybridRetriever:
    """Гибридный ретривер для поиска релевантных чанков по запросу.

    Алгоритм:
    1. Генерируем эмбеддинг запроса.
    2. Dense-поиск: ищем top_k ближайших векторов в Qdrant.
    3. Sparse-поиск: ищем top_k лучших совпадений по BM25.
    4. Объединяем через RRF (Reciprocal Rank Fusion).
    5. Возвращаем top_k объединённых результатов.
    """

    def __init__(
        self,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> None:
        """
        Args:
            dense_weight: Вес плотного поиска в итоговом ранжировании.
            sparse_weight: Вес BM25 в итоговом ранжировании.
        """
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._bm25_index = None  # TODO: инициализировать BM25Okapi при старте

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """Основной метод гибридного поиска.

        Args:
            query: Запрос пользователя в текстовом виде.
            top_k: Максимальное количество возвращаемых чанков.

        Returns:
            Список чанков, отсортированных по убыванию релевантности.
        """
        from rag.core.embeddings import get_embedding_service

        embedding_service = get_embedding_service()
        query_vector = await embedding_service.embed_text(query)

        dense_results = await self._dense_search(query_vector, top_k)

        # TODO: sparse_results = self._sparse_search(query, top_k)
        # TODO: merged = self._merge_results(dense_results, sparse_results)

        log.info("retrieve_complete", query_len=len(query), results=len(dense_results))
        return dense_results[:top_k]

    async def _dense_search(
        self,
        query_vector: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Поиск по косинусной близости векторов в Qdrant.

        Args:
            query_vector: Эмбеддинг запроса.
            top_k: Количество результатов.
        """
        from rag.core.config import settings
        from rag.database.vector_db import get_vector_store

        vector_store = await get_vector_store()
        results = await vector_store.search(
            collection=settings.qdrant_collection_name,
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=settings.retrieval_similarity_threshold,
        )

        return [
            RetrievedChunk(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ]

    def _sparse_search(
        self,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """BM25-поиск по тексту чанков.

        Args:
            query: Текстовый запрос.
            top_k: Количество результатов.
        """
        # TODO: BM25Okapi(corpus).get_top_n(tokenize(query), corpus, n=top_k)
        pass

    def _merge_results(
        self,
        dense: list[RetrievedChunk],
        sparse: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Объединяет результаты dense и sparse поиска через RRF.

        Reciprocal Rank Fusion: score_rrf(d) = sum(1 / (k + rank_i(d)))
        где k=60 (стандартный параметр RRF).

        Args:
            dense: Результаты плотного поиска.
            sparse: Результаты BM25-поиска.
        """
        # TODO: реализовать RRF с весами self._dense_weight и self._sparse_weight
        pass


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    """Возвращает singleton-экземпляр HybridRetriever."""
    global _retriever
    if _retriever is None:
        from rag.core.config import settings
        _retriever = HybridRetriever(
            dense_weight=settings.hybrid_search_weight_semantic,
            sparse_weight=settings.hybrid_search_weight_lexical,
        )
    return _retriever

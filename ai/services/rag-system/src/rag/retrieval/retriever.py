"""Ретривер с dense + sparse(BM25) поиском.

Dense-часть ищет в Qdrant, sparse-часть строится из сохранённых payload'ов
с полем `sparse_text`.
"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any

import structlog
from rank_bm25 import BM25Okapi

from rag.retrieval.sparse import tokenize_for_sparse

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
    3. Sparse-поиск: строим BM25 из сохранённых payload'ов.
    4. Объединяем результаты через weighted RRF.
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
        self._bm25_index: BM25Okapi | None = None
        self._bm25_docs: list[RetrievedChunk] = []
        self._bm25_corpus: list[list[str]] = []
        self._sparse_index_lock = asyncio.Lock()

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
        if not dense_results:
            log.info(
                "dense_search_relaxed_fallback",
                query_len=len(query),
                top_k=top_k,
                reason="no_results_with_threshold",
            )
            dense_results = await self._dense_search(query_vector, top_k, score_threshold=0.0)

        await self._ensure_sparse_index()
        sparse_results = self._sparse_search(query, top_k)
        merged = self._merge_results(dense_results, sparse_results)

        returned = min(len(merged), top_k)
        log.info(
            "retrieve_complete",
            query_len=len(query),
            top_k=top_k,
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            merged_count=len(merged),
            returned_count=returned,
            dense_weight=self._dense_weight,
            sparse_weight=self._sparse_weight,
        )
        return merged[:top_k]

    async def _dense_search(
        self,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None = None,
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
            score_threshold=score_threshold if score_threshold is not None else settings.retrieval_similarity_threshold,
        )

        log.info(
            "dense_search_result",
            collection=settings.qdrant_collection_name,
            returned=len(results),
            top_k=top_k,
            score_threshold=score_threshold if score_threshold is not None else settings.retrieval_similarity_threshold,
        )
        
        # 📊 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ РЕЗУЛЬТАТОВ ПОИСКА
        import os
        if os.environ.get("DEBUG_RETRIEVAL", "").lower() == "true":
            for i, r in enumerate(results, 1):
                log.info(
                    f"  ├─ Dense result #{i}",
                    score=r.score,
                    document_id=r.document_id,
                    chunk_id=r.chunk_id,
                    drug_id=r.metadata.get("drug_id"),
                )
                log.info(f"    Text: {r.text[:400]}...")
                log.info(f"    Metadata: {r.metadata}")

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
        if self._bm25_index is None or not self._bm25_docs:
            return []

        query_tokens = tokenize_for_sparse(query)
        scores = self._bm25_index.get_scores(query_tokens)

        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        results: list[RetrievedChunk] = []
        for index in ranked_indexes:
            if scores[index] <= 0:
                continue
            doc = self._bm25_docs[index]
            results.append(
                RetrievedChunk(
                    chunk_id=doc.chunk_id,
                    document_id=doc.document_id,
                    text=doc.text,
                    score=float(scores[index]),
                    metadata=doc.metadata,
                )
            )

        return results

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
        if not sparse:
            return dense

        k = 60.0
        merged: dict[str, RetrievedChunk] = {}
        scores: dict[str, float] = {}

        def add_ranked(results: list[RetrievedChunk], weight: float) -> None:
            for rank, chunk in enumerate(results, start=1):
                chunk_key = chunk.chunk_id
                if chunk_key not in merged:
                    merged[chunk_key] = chunk
                    scores[chunk_key] = 0.0
                scores[chunk_key] += weight / (k + rank)

        add_ranked(dense, self._dense_weight)
        add_ranked(sparse, self._sparse_weight)

        ranked = sorted(merged.values(), key=lambda chunk: scores[chunk.chunk_id], reverse=True)
        for chunk in ranked:
            chunk.score = scores[chunk.chunk_id]
        return ranked

    async def _ensure_sparse_index(self) -> None:
        """Ленивая загрузка BM25-индекса из сохранённых Qdrant payload'ов."""
        if self._bm25_index is not None:
            return

        async with self._sparse_index_lock:
            if self._bm25_index is not None:
                return

            from rag.core.config import settings
            from rag.database.vector_db import get_vector_store

            vector_store = await get_vector_store()
            documents = await vector_store.scroll_all(
                collection=settings.qdrant_collection_name,
                with_vectors=False,
            )

            self._bm25_docs = []
            self._bm25_corpus = []

            for document in documents:
                sparse_text = document.metadata.get("sparse_text") or document.text
                tokens = tokenize_for_sparse(str(sparse_text))
                if not tokens:
                    continue

                self._bm25_docs.append(document)
                self._bm25_corpus.append(tokens)

            self._bm25_index = BM25Okapi(self._bm25_corpus) if self._bm25_corpus else None
            log.info("sparse_index_loaded", documents=len(self._bm25_docs), corpus=len(self._bm25_corpus))


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

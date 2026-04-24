"""Реранкер результатов поиска.

После гибридного поиска результаты могут быть дополнительно
переупорядочены с учётом медицинского контекста пользователя:
аллергий, текущих препаратов, хронических диагнозов.
"""

from __future__ import annotations

from typing import Any

import structlog

from rag.retrieval.retriever import RetrievedChunk

log = structlog.get_logger()


class Reranker:
    """Переупорядочивает найденные чанки по медицинской релевантности.

    Стратегии реранкинга:
    1. Cross-encoder — нейросетевая оценка релевантности (query, chunk).
    2. Profile-aware — понижение рейтинга чанков с противопоказаниями
       для конкретного пользователя.
    3. Recency bias — предпочтение более актуальным документам.
    """

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        user_context: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Переупорядочивает чанки и возвращает top_k наиболее релевантных.

        Args:
            query: Исходный запрос пользователя.
            chunks: Список кандидатов из гибридного поиска.
            user_context: Медицинский профиль для profile-aware реранкинга.
            top_k: Итоговое количество чанков.

        Returns:
            Переупорядоченный список из top_k чанков.
        """
        # TODO:
        # 1. cross_encoder_scores = model.predict([(query, c.text) for c in chunks])
        # 2. Если user_context — применить profile penalties
        # 3. Пересортировать по итоговому score
        # 4. Вернуть top_k
        log.warning("reranker_not_implemented", chunks_count=len(chunks))
        return chunks[:top_k]

    def _apply_profile_penalties(
        self,
        chunks: list[RetrievedChunk],
        allergies: list[str],
        current_medications: list[str],
    ) -> list[RetrievedChunk]:
        """Снижает оценки чанков с противопоказаниями для профиля пользователя.

        Args:
            chunks: Список чанков для фильтрации.
            allergies: Список аллергенов пользователя.
            current_medications: Текущие препараты пользователя.
        """
        # TODO: простой keyword-matching по тексту чанка
        pass


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Возвращает singleton-экземпляр Reranker."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker

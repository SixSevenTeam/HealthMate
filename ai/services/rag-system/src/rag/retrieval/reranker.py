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

_ALLERGY_PENALTY = 0.3


class Reranker:
    """Переупорядочивает найденные чанки по медицинской релевантности.

    Стратегии реранкинга:
    1. Profile-aware — понижение рейтинга чанков с противопоказаниями
       для конкретного пользователя (keyword matching по аллергенам).
    2. Recency bias — предпочтение более актуальным документам.
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
                Ожидаемые ключи: "allergies" (list[str]), "current_medications" (list[str]).
            top_k: Итоговое количество чанков.

        Returns:
            Переупорядоченный список из top_k чанков.
        """
        if user_context:
            allergies = user_context.get("allergies") or []
            current_medications = user_context.get("current_medications") or []
            if allergies or current_medications:
                chunks = self._apply_profile_penalties(chunks, allergies, current_medications)
                chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
                log.info(
                    "reranker_profile_penalties_applied",
                    allergies_count=len(allergies),
                    medications_count=len(current_medications),
                    chunks_count=len(chunks),
                )

        return chunks[:top_k]

    def _apply_profile_penalties(
        self,
        chunks: list[RetrievedChunk],
        allergies: list[str],
        current_medications: list[str],
    ) -> list[RetrievedChunk]:
        """Снижает оценки чанков с противопоказаниями для профиля пользователя.

        Простой keyword-matching: если текст чанка содержит название аллергена
        (case-insensitive), score снижается на _ALLERGY_PENALTY.

        Args:
            chunks: Список чанков для фильтрации.
            allergies: Список аллергенов пользователя.
            current_medications: Текущие препараты пользователя (зарезервировано).
        """
        normalized_allergens = [a.lower().strip() for a in allergies if a]

        for chunk in chunks:
            text_lower = chunk.text.lower()
            for allergen in normalized_allergens:
                if allergen and allergen in text_lower:
                    chunk.score = max(0.0, chunk.score - _ALLERGY_PENALTY)
                    log.debug(
                        "allergy_penalty_applied",
                        chunk_id=chunk.chunk_id,
                        allergen=allergen,
                        new_score=chunk.score,
                    )
                    break

        return chunks


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Возвращает singleton-экземпляр Reranker."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker

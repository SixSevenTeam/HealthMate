"""Этапы медицинского диалога."""

from __future__ import annotations

from enum import Enum


class ConsultationStage(str, Enum):
    """Текущий этап диалоговой консультации.

    Переход между этапами происходит автоматически на основании
    количества заданных уточняющих вопросов и полноты собранного анамнеза.
    """

    # Этап 1: Сбор анамнеза (уточняющие вопросы, не более max_clarifying_questions)
    ANAMNESIS = "anamnesis_collection"

    # Этап 2: Синтез контекста (симптомы + профиль пользователя)
    SYNTHESIS = "context_synthesis"

    # Этап 3: Генерация рекомендаций с проверкой безопасности
    RECOMMENDATION = "recommendation"

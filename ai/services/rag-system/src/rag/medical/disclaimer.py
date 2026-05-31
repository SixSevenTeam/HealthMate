"""Медицинский дисклеймер для всех ответов RAG-системы.

Дисклеймер обязателен для каждого ответа системы пользователю.
Реэкспортирует константу из dialogue.prompts для удобного импорта.
"""

from __future__ import annotations

from rag.dialogue.prompts import MEDICAL_DISCLAIMER

__all__ = ["MEDICAL_DISCLAIMER", "inject_disclaimer"]


def inject_disclaimer(text: str) -> str:
    """Добавляет медицинский дисклеймер к тексту ответа.

    Args:
        text: Текст ответа системы.

    Returns:
        Текст с добавленным дисклеймером в конце.
    """
    return text + MEDICAL_DISCLAIMER

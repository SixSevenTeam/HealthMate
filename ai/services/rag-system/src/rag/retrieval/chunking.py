"""Сервис разбиения документов на чанки.

Использует гибридный метод:
1. Семантические границы — разбивка по узлам JSON-дерева (заголовки разделов).
2. Размерные ограничения — если узел слишком большой, дополнительное разбиение
   по абзацам с сохранением перекрытия (overlap) для связности контекста.

Метаданные каждого чанка включают section_path — путь в дереве документа,
что позволяет LLM понимать контекст раздела при формировании ответа.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from rag.core.config import settings

log = structlog.get_logger()


@dataclass
class Chunk:
    """Чанк документа с текстом и контекстными метаданными."""

    text: str
    metadata: dict[str, Any]
    chunk_index: int
    section_path: list[str] = field(default_factory=list)
    page_starts_at: int | None = None


class ChunkingService:
    """Разбивает JSON-дерево документа на чанки для векторизации.

    Стратегия:
    1. Обходим дерево (tree_json) узел за узлом.
    2. Каждый узел с content → кандидат в чанк.
    3. Если content > chunk_size → разбиваем по абзацам.
    4. Если content < min_chunk_size → объединяем с соседним чанком.
    5. Добавляем overlap (перекрытие) из текста соседних чанков.
    6. Сохраняем section_path для контекста LLM.
    """

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
        min_chunk_size: int = settings.min_chunk_size,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, json_data: dict[str, Any]) -> list[Chunk]:
        """Разбивает JSON-дерево документа на список чанков.

        Args:
            json_data: Иерархическое JSON-дерево из document-parser.
                       Ожидаемая структура: {"type": "root", "children": [...], "content": "..."}

        Returns:
            Список чанков, готовых к эмбеддингу.
        """
        # TODO: вызвать _traverse_tree(json_data, path=[]),
        #       затем _add_overlap(chunks)
        log.warning("chunk_document_not_implemented")
        pass

    def _traverse_tree(
        self,
        node: dict[str, Any],
        path: list[str],
    ) -> list[Chunk]:
        """Рекурсивно обходит дерево и собирает чанки из узлов.

        Args:
            node: Текущий узел дерева.
            path: Текущий путь заголовков от корня до этого узла.

        Returns:
            Список чанков из данного поддерева.
        """
        # TODO:
        # 1. Если node["content"] непустой → _split_by_size(content, path)
        # 2. Рекурсивно обойти node["children"]
        # 3. Объединить маленькие соседние чанки
        pass

    def _split_by_size(
        self,
        text: str,
        path: list[str],
        page_starts_at: int | None = None,
    ) -> list[Chunk]:
        """Разбивает длинный текст на чанки по размеру с перекрытием.

        Args:
            text: Текст узла для разбиения.
            path: Путь заголовков для метаданных чанка.
            page_starts_at: Номер страницы начала раздела.

        Returns:
            Список чанков из данного текста.
        """
        # TODO: разбивать по \n\n (абзацы), накапливая chunk_size символов,
        #       добавлять chunk_overlap символов из предыдущего чанка
        pass

    def _add_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        """Добавляет перекрытие между соседними чанками.

        Первые chunk_overlap символов следующего чанка добавляются в конец
        текущего. Это сохраняет контекст на границах разбиения.

        Args:
            chunks: Список чанков до добавления перекрытия.

        Returns:
            Список чанков с добавленным перекрытием.
        """
        # TODO: для каждого chunks[i] добавить chunks[i+1].text[:chunk_overlap]
        pass


_chunking_service: ChunkingService | None = None


def get_chunker() -> ChunkingService:
    """Возвращает singleton-экземпляр ChunkingService."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service

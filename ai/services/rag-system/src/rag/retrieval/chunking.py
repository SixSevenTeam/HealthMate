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
        raw_chunks = self._traverse_tree(json_data, path=[])
        merged = self._merge_small_chunks(raw_chunks)
        final = self._add_overlap(merged)

        for i, chunk in enumerate(final):
            chunk.chunk_index = i

        log.info("chunking_complete", raw=len(raw_chunks), merged=len(merged), final=len(final))
        return final

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
        chunks: list[Chunk] = []
        heading = node.get("heading", {})
        title = heading.get("title", "")
        page = heading.get("page_starts_at")

        current_path = path + [title] if title and title != "Document Root" else list(path)

        content = (node.get("content") or "").strip()
        if content:
            chunks.extend(self._split_by_size(content, current_path, page))

        for child in node.get("children", []):
            chunks.extend(self._traverse_tree(child, current_path))

        return chunks

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
        if len(text) <= self.chunk_size:
            return [
                Chunk(
                    text=text,
                    metadata={"section_path": list(path)},
                    chunk_index=0,
                    section_path=list(path),
                    page_starts_at=page_starts_at,
                )
            ]

        paragraphs = text.split("\n\n")
        chunks: list[Chunk] = []
        current_text = ""

        for para in paragraphs:
            candidate = (current_text + "\n\n" + para).strip() if current_text else para.strip()

            if len(candidate) > self.chunk_size and current_text:
                chunks.append(
                    Chunk(
                        text=current_text.strip(),
                        metadata={"section_path": list(path)},
                        chunk_index=0,
                        section_path=list(path),
                        page_starts_at=page_starts_at,
                    )
                )
                current_text = para.strip()
            else:
                current_text = candidate

        if current_text.strip():
            chunks.append(
                Chunk(
                    text=current_text.strip(),
                    metadata={"section_path": list(path)},
                    chunk_index=0,
                    section_path=list(path),
                    page_starts_at=page_starts_at,
                )
            )

        return chunks

    def _merge_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Объединяет слишком маленькие соседние чанки.

        Если чанк меньше min_chunk_size, присоединяет его к предыдущему.

        Args:
            chunks: Список чанков до объединения.

        Returns:
            Список чанков после объединения маленьких.
        """
        if not chunks:
            return []

        merged: list[Chunk] = [chunks[0]]

        for chunk in chunks[1:]:
            prev = merged[-1]
            if len(prev.text) < self.min_chunk_size:
                prev.text = prev.text + "\n\n" + chunk.text
                if chunk.section_path and chunk.section_path != prev.section_path:
                    prev.metadata["section_path"] = prev.section_path
            else:
                merged.append(chunk)

        return merged

    def _add_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        """Добавляет перекрытие между соседними чанками.

        Первые chunk_overlap символов следующего чанка добавляются в конец
        текущего. Это сохраняет контекст на границах разбиения.

        Args:
            chunks: Список чанков до добавления перекрытия.

        Returns:
            Список чанков с добавленным перекрытием.
        """
        if len(chunks) <= 1:
            return chunks

        for i in range(len(chunks) - 1):
            next_text = chunks[i + 1].text
            overlap_text = next_text[: self.chunk_overlap]
            if overlap_text:
                chunks[i].text = chunks[i].text + "\n...\n" + overlap_text

        return chunks


_chunking_service: ChunkingService | None = None


def get_chunker() -> ChunkingService:
    """Возвращает singleton-экземпляр ChunkingService."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service

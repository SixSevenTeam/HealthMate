"""Общие фикстуры для всех тестов document-parser."""

import pytest

from test.resources import load_json, load_text


@pytest.fixture
def sample_htm_simple() -> str:
    """Минимальный HTM-документ с заголовком, контентом и колонтитулом."""
    return load_text("request/processor/sample_simple.htm")


@pytest.fixture
def sample_htm_with_toc() -> str:
    """HTM с оглавлением (nav.toc) и разделами — TOC должен быть удалён."""
    return load_text("request/processor/sample_with_toc.htm")


@pytest.fixture
def sample_htm_with_tables() -> str:
    """HTM с таблицей дозировок — таблица должна сохраниться."""
    return load_text("request/processor/sample_with_tables.htm")


@pytest.fixture
def sample_htm_cp1251(tmp_path) -> str:
    """HTM-файл в кодировке cp1251 — возвращает путь к файлу."""
    content = "<html><body><h1>Парацетамол</h1><p>Препарат.</p></body></html>"
    file_path = tmp_path / "cp1251_doc.htm"
    file_path.write_bytes(content.encode("cp1251"))
    return str(file_path)


@pytest.fixture
def sample_markdown_flat() -> str:
    """Markdown без заголовков — весь текст идёт в root content."""
    return load_text("request/processor/sample_markdown_flat.md")


@pytest.fixture
def sample_markdown_nested() -> str:
    """Markdown с вложенными заголовками."""
    return load_text("request/processor/sample_markdown_nested.md")


@pytest.fixture
def sample_incoming_event_dict() -> dict:
    """Словарь в wire-формате Java-бэкенда (camelCase)."""
    return load_json("request/domain/incoming_event.json")

"""Общие фикстуры для всех тестов document-parser."""

import pytest


@pytest.fixture
def sample_htm_simple() -> str:
    """Минимальный HTM-документ с заголовком, контентом и колонтитулом."""
    return """
    <html>
    <body>
        <header><p>Шапка документа</p></header>
        <h1>Парацетамол</h1>
        <p>Жаропонижающее и обезболивающее средство.</p>
        <footer><p>Страница 1</p></footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_htm_with_toc() -> str:
    """HTM с оглавлением (nav.toc) и разделами — TOC должен быть удалён."""
    return """
    <html>
    <body>
        <nav class="toc">
            <ul><li>Показания</li><li>Противопоказания</li></ul>
        </nav>
        <h1>Показания к применению</h1>
        <p>Головная боль, жар, боли в мышцах.</p>
        <h2>Противопоказания</h2>
        <p>Аллергия на парацетамол.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_htm_with_tables() -> str:
    """HTM с таблицей дозировок — таблица должна сохраниться."""
    return """
    <html>
    <body>
        <h1>Дозировка</h1>
        <table>
            <tr><th>Возраст</th><th>Доза</th></tr>
            <tr><td>Взрослые</td><td>500 мг</td></tr>
            <tr><td>Дети</td><td>250 мг</td></tr>
        </table>
    </body>
    </html>
    """


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
    return "Описание препарата.\n\nПрименяется при боли и жаре."


@pytest.fixture
def sample_markdown_nested() -> str:
    """Markdown с вложенными заголовками."""
    return (
        "# Инструкция по применению\n\n"
        "Общее описание.\n\n"
        "## Показания\n\n"
        "Головная боль.\n\n"
        "## Противопоказания\n\n"
        "Аллергия.\n\n"
        "### Особые группы\n\n"
        "Беременность: с осторожностью.\n"
    )


@pytest.fixture
def sample_incoming_event_dict() -> dict:
    """Словарь в wire-формате Java-бэкенда (camelCase)."""
    return {
        "id": "doc-test-123",
        "minIoBucket": "raw-documents",
        "filePath": "paracetamol.htm",
    }

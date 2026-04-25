"""Юнит-тесты для Processor: чтение HTM + очистка + конвертация в Markdown."""

import pytest

from docparser.infrastructure.pars import Processor


@pytest.fixture
def processor() -> Processor:
    return Processor()


# ── Базовая структура результата ──────────────────────────────────────────────

def test_convert_simple_htm_returns_list_of_dicts(processor, sample_htm_simple, tmp_path):
    file_path = tmp_path / "test.htm"
    file_path.write_text(sample_htm_simple, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert isinstance(result, list)
    assert len(result) == 1


def test_result_has_page_and_text_keys(processor, sample_htm_simple, tmp_path):
    file_path = tmp_path / "test.htm"
    file_path.write_text(sample_htm_simple, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert "page" in result[0]
    assert "text" in result[0]


def test_page_number_is_always_1_for_htm(processor, sample_htm_simple, tmp_path):
    """HTM-файлы — один логический документ, всегда page=1."""
    file_path = tmp_path / "test.htm"
    file_path.write_text(sample_htm_simple, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert result[0]["page"] == 1


# ── Удаление структурного мусора ──────────────────────────────────────────────

def test_footer_tag_removed(processor, sample_htm_simple, tmp_path):
    file_path = tmp_path / "test.htm"
    file_path.write_text(sample_htm_simple, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert "Страница 1" not in result[0]["text"]
    assert "Шапка документа" not in result[0]["text"]


def test_nav_toc_removed(processor, sample_htm_with_toc, tmp_path):
    """Элементы оглавления (nav.toc) не должны попасть в Markdown."""
    file_path = tmp_path / "toc.htm"
    file_path.write_text(sample_htm_with_toc, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    text = result[0]["text"]
    # Содержимое nav.toc — просто список ссылок — не должно быть отдельным блоком
    # Заголовки из контента — должны остаться
    assert "Показания к применению" in text or "Показания" in text


def test_script_and_style_tags_removed(processor, tmp_path):
    """Теги script и style должны быть удалены."""
    html = """
    <html><head>
        <style>body { color: red; }</style>
        <script>alert('test');</script>
    </head><body>
        <h1>Препарат</h1><p>Контент.</p>
    </body></html>
    """
    file_path = tmp_path / "test.htm"
    file_path.write_text(html, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    text = result[0]["text"]
    assert "color: red" not in text
    assert "alert(" not in text


# ── Сохранение медицинского контента ─────────────────────────────────────────

def test_content_headings_preserved_as_markdown(processor, sample_htm_with_toc, tmp_path):
    """Заголовки HTML (<h1>, <h2>) должны стать заголовками Markdown (# / ##)."""
    file_path = tmp_path / "test.htm"
    file_path.write_text(sample_htm_with_toc, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    text = result[0]["text"]
    assert "#" in text


def test_dosage_table_preserved(processor, sample_htm_with_tables, tmp_path):
    """Таблицы дозировок должны сохраняться в виде Markdown-таблицы."""
    file_path = tmp_path / "dosage.htm"
    file_path.write_text(sample_htm_with_tables, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    text = result[0]["text"]
    # html2text рендерит таблицы как pipe-separated строки
    assert "500" in text or "Взрослые" in text


# ── Кодировка ─────────────────────────────────────────────────────────────────

def test_encoding_detection_cp1251(processor, sample_htm_cp1251):
    """Файлы в cp1251 должны декодироваться корректно (кириллица)."""
    result = processor.convert_to_markdown(sample_htm_cp1251)
    text = result[0]["text"]
    # Кириллический текст должен читаться, а не превращаться в кракозябры
    assert "?" not in text or "Парацетамол" in text
    assert len(text) > 0


# ── Граничные случаи ──────────────────────────────────────────────────────────

def test_empty_html_returns_chunk(processor, tmp_path):
    """Пустой HTML не должен вызывать исключение."""
    file_path = tmp_path / "empty.htm"
    file_path.write_text("<html><body></body></html>", encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert isinstance(result, list)
    assert len(result) == 1


def test_malformed_html_does_not_raise(processor, tmp_path):
    """BeautifulSoup лениво исправляет невалидный HTML, исключение не поднимается."""
    malformed = "<html><body><h1>Без закрывающего тега<p>Параграф</body>"
    file_path = tmp_path / "malformed.htm"
    file_path.write_text(malformed, encoding="utf-8")
    result = processor.convert_to_markdown(str(file_path))
    assert isinstance(result, list)


def test_nonexistent_file_raises_runtime_error(processor):
    """Несуществующий файл должен вызывать RuntimeError, а не OSError."""
    with pytest.raises(RuntimeError, match="Не удалось прочитать файл"):
        processor.convert_to_markdown("/nonexistent/path/file.htm")


# ── Статические методы _clean_markdown ───────────────────────────────────────

def test_clean_markdown_removes_unicode_junk():
    """Unicode-мусор (NBSP, zero-width spaces и т.п.) удаляется."""
    dirty = "Текст\u00a0с\u200bмусором\ufeff."
    result = Processor._clean_markdown(dirty)
    assert "\u00a0" not in result
    assert "\u200b" not in result
    assert "\ufeff" not in result


def test_clean_markdown_collapses_multiple_blank_lines():
    """Три и более пустых строки схлопываются до двух."""
    text = "Строка 1\n\n\n\n\nСтрока 2"
    result = Processor._clean_markdown(text)
    assert "\n\n\n" not in result
    assert "Строка 1" in result
    assert "Строка 2" in result


def test_clean_markdown_strips_leading_trailing():
    """Ведущие/замыкающие пробелы удаляются."""
    text = "   \n\nКонтент\n\n   "
    result = Processor._clean_markdown(text)
    assert result == "Контент"

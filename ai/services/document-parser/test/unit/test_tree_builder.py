"""Юнит-тесты для MarkdownTreeBuilder: построение JSON-дерева из Markdown."""

import pytest

from docparser.infrastructure.pars.tree_builder import MarkdownTreeBuilder


@pytest.fixture
def builder() -> MarkdownTreeBuilder:
    return MarkdownTreeBuilder()


def _pages(text: str, page: int = 1) -> list[dict]:
    """Вспомогательная функция: создаёт список чанков из строки."""
    return [{"page": page, "text": text}]


# ── Структура корневого узла ──────────────────────────────────────────────────

def test_build_tree_returns_dict(builder):
    result = builder.build_tree([])
    assert isinstance(result, dict)


def test_empty_pages_returns_root_node(builder):
    """Пустой ввод → корневой узел без дочерних элементов."""
    result = builder.build_tree([])
    assert result["type"] == "root"
    assert result["children"] == []


def test_root_node_structure(builder):
    """Корневой узел должен содержать все обязательные поля."""
    result = builder.build_tree([])
    assert result["heading"]["depth"] == 0
    assert result["heading"]["title"] == "Document Root"
    assert result["heading"]["page_starts_at"] == 1
    assert "content" in result


# ── Плоский текст без заголовков ──────────────────────────────────────────────

def test_flat_text_becomes_root_content(builder, sample_markdown_flat):
    """Текст без заголовков идёт в content корневого узла."""
    result = builder.build_tree(_pages(sample_markdown_flat))
    assert "Описание препарата" in result["content"]
    assert result["children"] == []


# ── Создание дочерних узлов ───────────────────────────────────────────────────

def test_h1_creates_first_level_child(builder):
    result = builder.build_tree(_pages("# Заголовок 1\n\nТекст раздела."))
    assert len(result["children"]) == 1
    assert result["children"][0]["heading"]["depth"] == 1
    assert result["children"][0]["heading"]["title"] == "Заголовок 1"


def test_h2_nested_under_h1(builder):
    md = "# Раздел 1\n\n## Подраздел 1.1\n\nТекст."
    result = builder.build_tree(_pages(md))
    assert len(result["children"]) == 1
    h1 = result["children"][0]
    assert len(h1["children"]) == 1
    assert h1["children"][0]["heading"]["depth"] == 2


def test_second_h1_creates_sibling_not_child(builder):
    """Второй H1 должен быть сиблингом первого, а не его потомком."""
    md = "# Раздел 1\n\n# Раздел 2\n"
    result = builder.build_tree(_pages(md))
    assert len(result["children"]) == 2
    assert result["children"][0]["heading"]["title"] == "Раздел 1"
    assert result["children"][1]["heading"]["title"] == "Раздел 2"


def test_h3_after_h1_skipping_h2_still_works(builder):
    """Пропуск уровня (H1 → H3) не должен вызывать ошибку."""
    md = "# Раздел\n\n### Глубокий подраздел\n"
    result = builder.build_tree(_pages(md))
    h1 = result["children"][0]
    assert len(h1["children"]) == 1
    assert h1["children"][0]["heading"]["depth"] == 3


def test_deeply_nested_headings_h1_to_h4(builder):
    """Проверяем вложенность до 4-го уровня."""
    md = "# H1\n## H2\n### H3\n#### H4\n"
    result = builder.build_tree(_pages(md))
    h1 = result["children"][0]
    h2 = h1["children"][0]
    h3 = h2["children"][0]
    h4 = h3["children"][0]
    assert h4["heading"]["depth"] == 4


# ── Контент узлов ─────────────────────────────────────────────────────────────

def test_content_assigned_to_correct_section(builder):
    """Текст после заголовка должен попасть в content того же раздела."""
    md = "# Показания\n\nГоловная боль.\n"
    result = builder.build_tree(_pages(md))
    h1 = result["children"][0]
    assert "Головная боль" in h1["content"]


def test_content_stripped_of_whitespace(builder):
    """Content должен быть обрезан — без ведущих/замыкающих пробелов."""
    md = "# Раздел\n\n  Текст с отступами.  \n"
    result = builder.build_tree(_pages(md))
    content = result["children"][0]["content"]
    assert content == content.strip()


# ── Работа с несколькими страницами ───────────────────────────────────────────

def test_multiple_pages_merged_correctly(builder):
    """Два чанка с разных страниц должны объединяться в одно дерево."""
    pages = [
        {"page": 1, "text": "# Раздел А\n\nТекст А."},
        {"page": 2, "text": "# Раздел Б\n\nТекст Б."},
    ]
    result = builder.build_tree(pages)
    assert len(result["children"]) == 2


def test_heading_page_starts_at_correct_value(builder):
    """page_starts_at должен соответствовать странице, на которой встретился заголовок."""
    pages = [
        {"page": 3, "text": "# Раздел\n\nТекст."},
    ]
    result = builder.build_tree(pages)
    assert result["children"][0]["heading"]["page_starts_at"] == 3

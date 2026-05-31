from __future__ import annotations

import re
from typing import Any

import html2text
import structlog
from bs4 import BeautifulSoup, Tag
from charset_normalizer import from_path

log = structlog.get_logger()

_RE_UNICODE_JUNK = re.compile(r"[\u00a0\u200b\u200c\u200d\ufeff\u2028\u2029]")
_RE_MULTIPLE_BLANK = re.compile(r"\n{3,}")
_RE_NORMALIZE_SPACES = re.compile(r"\s+")

_INDICATION_HEADINGS = {
    "показания",
    "показания к применению",
    "область применения",
    "особые указания",
    "фармакологическое действие",
    "свойства",
    "рекомендации по применению",
}

_SECTION_HEADINGS = {
    "показания",
    "показания к применению",
    "область применения",
    "противопоказания",
    "побочное действие",
    "побочные действия",
    "способ применения и дозы",
    "режим дозирования",
    "взаимодействие с другими лекарственными средствами",
    "особые указания",
    "фармакологическое действие",
    "свойства",
    "рекомендации по применению",
    "условия хранения и сроки годности",
}


def normalize_heading_title(title: str) -> str:
    """Нормализует заголовок для классификации секций."""
    normalized = _RE_NORMALIZE_SPACES.sub(" ", title).strip().lower()
    return normalized.rstrip(":;.,")


def is_indication_heading(title: str) -> bool:
    """Возвращает True, если заголовок относится к показаниям к применению."""
    normalized = normalize_heading_title(title)
    return normalized in _INDICATION_HEADINGS or normalized.startswith("показания ")


class Processor:
    """Приводит Vidal HTML к очищенному Markdown."""

    _BOILERPLATE_SELECTORS: list[str] = [
        "header",
        "footer",
        "nav",
        "script",
        "style",
        "[id*='toc']",
        "[class*='toc']",
        "[id*='contents']",
        "[class*='contents']",
        "[id*='page-number']",
        "[class*='page-number']",
        "[class*='pagenum']",
        "[class*='menu']",
        "[class*='navigation']",
        "[id*='navigation']",
        "p.menu",
    ]

    def convert_to_markdown(self, file_path: str) -> list[dict[str, Any]]:
        log.debug("processor_start", file_path=file_path)

        raw_html = self._read_html(file_path)
        soup = self._clean_html(raw_html)
        images = self._extract_images(soup)
        markdown = self._html_to_markdown(soup)
        cleaned = self._clean_markdown(markdown)

        return [{"page": 1, "text": cleaned, "images": images}]

    def _read_html(self, file_path: str) -> str:
        detected = from_path(file_path).best()
        encoding = detected.encoding if detected and detected.encoding else "utf-8"

        with open(file_path, encoding=encoding, errors="replace") as file_handle:
            return file_handle.read()

    def _clean_html(self, html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "lxml")

        content_table = soup.find("table", id="info")
        if content_table is not None:
            soup = BeautifulSoup(str(content_table), "lxml")

        self._promote_section_headings(soup)

        for top_link in soup.find_all("a", href="#top"):
            parent_td = top_link.find_parent("td")
            if parent_td is not None:
                parent_td.decompose()
            else:
                top_link.decompose()

        for selector in self._BOILERPLATE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

        return soup

    def _promote_section_headings(self, soup: BeautifulSoup) -> None:
        for bold_tag in soup.find_all("b"):
            parent = bold_tag.parent
            if not isinstance(parent, Tag):
                continue

            if not self._is_leading_child(bold_tag, parent):
                continue

            header_title = normalize_heading_title(bold_tag.get_text(" ", strip=True))
            if header_title in _SECTION_HEADINGS or is_indication_heading(header_title):
                bold_tag.name = "h2"

    @staticmethod
    def _is_leading_child(child: Tag, parent: Tag) -> bool:
        """Проверяет, является ли child первым значимым элементом в parent.
        
        Игнорирует:
        - пусто текстовые узлы
        - якоря (пустые <a> с атрибутом name)
        """
        for direct_child in parent.contents:
            if isinstance(direct_child, str):
                if not direct_child.strip():
                    continue
                return direct_child is child
            
            if isinstance(direct_child, Tag):
                # Пропускаем якоря с только атрибутом name (навигация)
                if direct_child.name == "a" and direct_child.get("name") and not direct_child.get_text(strip=True):
                    continue
                return direct_child is child
        
        return False

    def _extract_images(self, soup: BeautifulSoup) -> list[str]:
        images: list[str] = []
        for image in soup.find_all("img"):
            src = image.get("src")
            if src and "vidal" not in src.lower():
                images.append(src)
        return images

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        converter = html2text.HTML2Text()
        converter.body_width = 0
        converter.ignore_images = True
        converter.ignore_tables = False
        converter.protect_links = False
        converter.ul_item_mark = "-"
        return converter.handle(str(soup))

    @staticmethod
    def _clean_markdown(text: str) -> str:
        text = _RE_UNICODE_JUNK.sub(" ", text)
        text = _RE_MULTIPLE_BLANK.sub("\n\n", text)
        return text.strip()


class MarkdownTreeBuilder:
    """Строит JSON-дерево документа из markdown-чанков."""

    def __init__(self) -> None:
        self._header_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    def build_tree(self, pages_data: list[dict[str, Any]]) -> dict[str, Any]:
        root: dict[str, Any] = {
            "type": "root",
            "heading": {"depth": 0, "title": "Document Root", "page_starts_at": 1},
            "content": "",
            "images": [],
            "children": [],
        }

        stack: list[dict[str, Any]] = [root]

        for page in pages_data:
            page_num = page["page"]

            if page.get("images"):
                root["images"].extend(page["images"])

            for line in page["text"].split("\n"):
                match = self._header_pattern.match(line)
                if match is not None:
                    depth = len(match.group(1))
                    title = match.group(2).strip().rstrip(":;.,")

                    new_node: dict[str, Any] = {
                        "type": "section",
                        "heading": {"depth": depth, "title": title, "page_starts_at": page_num},
                        "content": "",
                        "children": [],
                    }

                    while len(stack) > 1 and stack[-1]["heading"]["depth"] >= depth:
                        stack.pop()

                    stack[-1]["children"].append(new_node)
                    stack.append(new_node)
                else:
                    cleaned_line = line.strip()
                    if cleaned_line or stack[-1]["content"]:
                        stack[-1]["content"] += line + "\n"

        self._clean_content(root)
        root["images"] = list(set(root["images"]))
        return root

    def _clean_content(self, node: dict[str, Any]) -> None:
        node["content"] = node["content"].strip()
        for child in node["children"]:
            self._clean_content(child)
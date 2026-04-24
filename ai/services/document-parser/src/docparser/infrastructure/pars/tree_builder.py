from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger()


"""Строит древовидную структуру JSON из Markdown-чанков по страницам.

    Алгоритм:
    1. Корневой узел (depth=0) — «Document Root».
    2. Стек предков — позволяет вложить узел на нужный уровень.
    3. Каждый заголовок (# / ## / ...) создаёт новый узел-раздел.
    4. Не-заголовочные строки добавляются в content текущего узла.
    5. После обхода всех страниц — обрезаем пробелы в content.
    + - хоть какая-то структура
    - - очень маленькая структура, могут быть проблемы в случае если весь файл из 1 заголовка. 
    (надо подумать по поводу того, чтобы по жирному шрифту выделять заголовки)
    решение - я <b> превращу в <h2> при парсинге :)
    """
class MarkdownTreeBuilder:

    def __init__(self) -> None:
        self._header_pattern = re.compile(r"^(#{1,6})\s+(.*)")


    """Строит иерархическое дерево из списка Markdown-чанков.
            Args:
                pages_data: Список словарей {"page": int, "text": str, "images": list[str]}}.

            Returns:
                Словарь с иерархической структурой документа.
            """
    def build_tree(self, pages_data: list[dict[str, Any]]) -> dict[str, Any]:

        log.debug("tree_build_start", page_count=len(pages_data))

        root: dict[str, Any] = {
            "type": "root",
            "heading": {
                "depth": 0,
                "title": "Document Root",
                "page_starts_at": 1,
            },
            "content": "",
            "images": [],
            "children": [],
        }

        stack: list[dict[str, Any]] = [root]

        for page in pages_data:
            page_num = page["page"]

            if "images" in page and page["images"]:
                root["images"].extend(page["images"])

            lines = page["text"].split("\n")

            for line in lines:
                match = self._header_pattern.match(line)

                if match:
                    depth = len(match.group(1))
                    title = match.group(2).strip()

                    new_node: dict[str, Any] = {
                        "type": "section",
                        "heading": {
                            "depth": depth,
                            "title": title,
                            "page_starts_at": page_num,
                        },
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

        # если 2 одинаковые фотки, чтобы не было дублей - через сет
        root["images"] = list(set(root["images"]))

        node_count = self._count_nodes(root)
        log.debug("tree_build_complete", node_count=node_count)

        return root

    """Рекурсивно обрезает пробелы в content всех узлов."""
    def _clean_content(self, node: dict[str, Any]) -> None:
        node["content"] = node["content"].strip()
        for child in node["children"]:
            self._clean_content(child)

    """Считает суммарное количество узлов в дереве (для debug-лога)."""
    @staticmethod
    def _count_nodes(node: dict[str, Any]) -> int:
        count = 1
        for child in node.get("children", []):
            count += MarkdownTreeBuilder._count_nodes(child)
        return count
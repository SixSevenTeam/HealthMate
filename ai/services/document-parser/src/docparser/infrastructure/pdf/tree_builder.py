import re
import json
from typing import Any, Dict, List


class MarkdownTreeBuilder:

    def __init__(self) -> None:
        self._header_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    def build_tree(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:

        root: Dict[str, Any] = {
            "type": "root",
            "heading": {
                "depth": 0,
                "title": "Document Root",
                "page_starts_at": 1
            },
            "content": "",
            "children": []
        }

        stack: List[Dict[str, Any]] = [root]

        for page in pages_data:
            page_num = page["page"]
            lines = page["text"].split('\n')

            for line in lines:
                match = self._header_pattern.match(line)

                if match:
                    # Нашли новый заголовок
                    depth = len(match.group(1))
                    title = match.group(2).strip()

                    new_node = {
                        "type": "section",
                        "heading": {
                            "depth": depth,
                            "title": title,
                            "page_starts_at": page_num
                        },
                        "content": "",
                        "children": []
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
        return root

    def _clean_content(self, node: Dict[str, Any]) -> None:
        node["content"] = node["content"].strip()
        for child in node["children"]:
            self._clean_content(child)
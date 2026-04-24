from __future__ import annotations

import re
from typing import Any

import html2text
import structlog
from bs4 import BeautifulSoup
from charset_normalizer import from_path

log = structlog.get_logger()

# Регулярные выражения для постобработки Markdown
_RE_UNICODE_JUNK = re.compile(
    r"[\u00a0\u200b\u200c\u200d\ufeff\u2028\u2029]"
)
_RE_MULTIPLE_BLANK = re.compile(r"\n{3,}")


"""Конвертирует HTM/HTML-файлы инструкций к лекарствам в чанки Markdown.

    Файлы небольшие (одна инструкция = один документ), поэтому всегда
    возвращается единственный чанк с page=1.  Контент максимально сохраняется:
    удаляется только структурный chrome (header, footer, nav, TOC, скрипты).
    """
class Processor:

    # CSS-селекторы элементов, которые считаются структурным мусором
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
        "[class*='page-number']",
        "[class*='pagenum']",
        "[class*='menu']",
        "[class*='navigation']",
        "[id*='navigation']",
        "p.menu",
    ]
    # _BOILERPLATE_SELECTORS: list[str] = [ # более короткий вариант
    #     "script",
    #     "style",
    #     "[id*='toc']",
    #     "[class*='toc']",
    #     "p.menu",  # Точный селектор для меню
    # ]

    """Основной pipeline: HTM-файл -> список чанков {"page": int, "text": str}.

        Args:
            file_path: Путь к локальному HTM/HTML-файлу.

        Returns:
            Список с одним элементом: [{"page": 1, "text": "<markdown>", "images": images}].
        да, я подумал - фотки тут будут чисто в формате: мы просто достали ссылку на них и все. Как и че и кто будет чет
        с ними делать - не наша забота

        Raises:
            RuntimeError: Если файл не удалось прочитать.
        """
    def convert_to_markdown(self, file_path: str) -> list[dict[str, Any]]:
        log.debug("processor_start", file_path=file_path)

        try:
            raw_html = self._read_html(file_path)
        except OSError as exc:
            log.error("processor_read_failed", file_path=file_path, error=str(exc))
            raise RuntimeError(f"Не удалось прочитать файл: {file_path}") from exc

        # чистка
        soup = self._clean_html(raw_html)

        # отдельно фотки (чтоб хотябы получить название фотки, потом придумать - типа в s3 хранить еще и фотки и
        # по имени оплучать ссылку на фотку)
        images = self._extract_images(soup)

        # конверт
        markdown = self._html_to_markdown(soup)
        cleaned = self._clean_markdown(markdown)

        log.debug(
            "processor_complete",
            file_path=file_path,
            output_chars=len(cleaned),
        )

        if not cleaned:
            log.warning("processor_empty_result", file_path=file_path)

        return [{"page": 1, "text": cleaned,
                 "images": images
                 }]

    """
    Читает файл с автоопределением кодировки.
    """
    def _read_html(self, file_path: str) -> str:
        results = from_path(file_path)
        best = results.best()

        if best is not None and best.encoding:
            encoding = best.encoding
            log.debug("encoding_detected", file_path=file_path, encoding=encoding)
        else:
            encoding = "utf-8"
            log.warning(
                "encoding_detection_failed",
                file_path=file_path,
                fallback=encoding,
            )

        with open(file_path, encoding=encoding, errors="replace") as fh:
            return fh.read()

    # def _clean_html(self, html: str) -> BeautifulSoup:
    #   # вариант для простой очистки - сохраняем практически все
    #     soup = BeautifulSoup(html, "lxml")
    #     removed = 0
    #
    #     for selector in self._BOILERPLATE_SELECTORS:
    #         for tag in soup.select(selector):
    #             tag.decompose()
    #             removed += 1
    #
    #     log.debug("html_cleaned", removed_elements=removed)
    #     return soup

    """Чистит HTM файл."""
    def _clean_html(self, html: str) -> BeautifulSoup:
        # вариант WHITELIST подход (я чекнул 1 файл и верю, что у всех такая же структура)
        soup = BeautifulSoup(html, "lxml")

        content_table = soup.find("table", id="info")
        if content_table:
            soup = BeautifulSoup(str(content_table), "lxml")
        else:
            log.warning("table_info_not_found", msg="Fallback to full HTML parsing")

        # Ищем все div с атрибутом colref (разделы инструкции)
        for section_div in soup.find_all("div", attrs={"colref": True}):
            # Находим в нем первый тег <b>
            header_b = section_div.find("b")
            if header_b:
                # Превращаем <b> в <h2>. 
                header_b.name = "h2"

        # Удаляем ссылку "Вернуться наверх" вместе с её родительским <td> или <tr>,
        # чтобы не оставалось пустых табличных строк
        for a_tag in soup.find_all("a", href="#top"):
            parent_td = a_tag.find_parent("td")
            if parent_td:
                parent_td.decompose()
            else:
                a_tag.decompose()

        # Удаляем оставшийся мусор по селекторам
        for selector in self._BOILERPLATE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

        return soup

    """Извлекает ссылки на изображения из очищенного HTML."""
    def _extract_images(self, soup: BeautifulSoup) -> list[str]:

        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                # (я сомневаюсь что видаль упадет вовнутрь, но лучше перебздеть, чем...)
                if "vidal" not in src.lower():
                    images.append(src)
        return images

    """Конвертирует очищенный HTML в Markdown через html2text.

            Настройки конвертера:
            - body_width=0: без искусственных переносов строк
            - ignore_images=True: убираем [[image]]-шум
            - ignore_tables=False: таблицы дозировок — медицинский контент
            - protect_links=False: не экранируем ссылки
            """
    def _html_to_markdown(self, soup: BeautifulSoup) -> str:

        converter = html2text.HTML2Text()
        converter.body_width = 0
        converter.ignore_images = True
        converter.ignore_tables = False
        converter.protect_links = False
        converter.ul_item_mark = "-"

        return converter.handle(str(soup))

    """Постобработка Markdown: убирает unicode-мусор и лишние пустые строки."""
    @staticmethod
    def _clean_markdown(text: str) -> str:
        # Заменяем unicode-артефакты на обычный пробел
        text = _RE_UNICODE_JUNK.sub(" ", text)

        # Три и более пустые строки подряд -> две
        text = _RE_MULTIPLE_BLANK.sub("\n\n", text)
        return text.strip()
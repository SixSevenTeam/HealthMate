from __future__ import annotations

import re
from typing import Any

import fitz  # PyMuPDF
import pymupdf4llm
import structlog

logger = structlog.get_logger()

_RE_PAGE_NUMBER = re.compile(
    r"^\s*[-—–]?\s*(?!(?:19|20)\d{2}\s*$)\d{1,4}\s*[-—–]?\s*$",
    re.MULTILINE,
)

_RE_HORIZONTAL_RULE = re.compile(
    r"^\s*[-=_*]{3,}\s*$", re.MULTILINE
)
_RE_MULTIPLE_BLANK = re.compile(r"\n{3,}")
_RE_UNICODE_JUNK = re.compile(
    r"[\u00a0\u200b\u200c\u200d\ufeff\u2028\u2029]"
)


class PageChunk:
    __slots__ = ("page", "text")

    def __init__(self, page: int, text: str) -> None:
        self.page = page
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "text": self.text}


class PDFProcessor:
    def convert_to_markdown(self, pdf_path: str) -> list[dict[str, Any]]:
        """PDF → список ``{"page": N, "text": "..."}`` по страницам.

        Returns:
            Список словарей с ключами ``page`` (int) и ``text`` (str).
        """
        doc: fitz.Document | None = None
        try:
            logger.info("pdf_conversion_start", path=pdf_path)

            # ── Открываем PDF один раз ────────────────────────────
            doc = fitz.open(pdf_path)

            # ── Динамически вычисляем отступы (margins) ───────────
            margin_top, margin_bottom = self._calculate_dynamic_margins(doc)
            logger.info(
                "pdf_margins_calculated",
                margin_top=round(margin_top, 2),
                margin_bottom=round(margin_bottom, 2)
            )

            # ── Конвертация с page_chunks=True ────────────────────
            # Порядок margins — PyMuPDF-геометрия: (left, top, right, bottom).
            raw_chunks: list[dict] = pymupdf4llm.to_markdown(
                doc,
                page_chunks=True,
                margins=(0, margin_top, 0, margin_bottom),
            )

            # ── Очистка каждой страницы ───────────────────────────
            result: list[PageChunk] = []
            for idx, chunk in enumerate(raw_chunks):
                try:
                    if isinstance(chunk, dict):
                        # Пробуем структуру как в рабочей версии
                        metadata = chunk.get("metadata", {})
                        page_num = metadata.get("page") if isinstance(metadata, dict) else None

                        # Фоллбэк на прямой ключ (вдруг версия библиотеки другая)
                        if page_num is None:
                            page_num = chunk.get("page") or chunk.get("page_no")

                        # Фоллбэк на индекс
                        if page_num is None:
                            page_num = idx + 1

                        text = chunk.get("text", "")
                    else:
                        text = str(chunk)
                        page_num = idx + 1

                    cleaned = self._clean_page(text)
                    if cleaned:
                        result.append(PageChunk(page=int(page_num), text=cleaned))
                except Exception as e:
                    logger.error("chunk_error", idx=idx, error=str(e), chunk=repr(chunk)[:100])
                    continue

            logger.info(
                "pdf_conversion_ok",
                path=pdf_path,
                total_pages=len(raw_chunks),
                result_pages=len(result),
            )
            return [c.to_dict() for c in result]

        except Exception as exc:
            logger.error(
                "pdf_conversion_failed", error=str(exc), path=pdf_path
            )
            raise RuntimeError(
                f"Не удалось сконвертировать PDF: {exc}"

            ) from exc
        finally:
            if doc is not None:
                doc.close()

    @staticmethod
    def _calculate_dynamic_margins(doc: fitz.Document, sample_size: int = 5) -> tuple[float, float]:

        if doc.page_count < 2:
            return 0.0, 0.0

        pages_to_check = min(doc.page_count, sample_size)
        page_height = doc[0].rect.height

        top_zone = page_height * 0.15
        bottom_zone = page_height * 0.85

        max_header_y = 0.0
        min_footer_y = page_height

        for i in range(pages_to_check):
            blocks = doc[i].get_text("blocks")
            for b in blocks:
                if b[6] != 0:
                    continue

                text = b[4].strip()
                if not text:
                    continue

                y0, y1 = b[1], b[3]

                if y1 < top_zone and (len(text) < 60 or text.isdigit()):
                    max_header_y = max(max_header_y, y1)

                if y0 > bottom_zone and (len(text) < 60 or text.isdigit()):
                    min_footer_y = min(min_footer_y, y0)

        margin_top = (max_header_y + 5) if max_header_y > 0 else 0.0
        margin_bottom = (page_height - min_footer_y + 5) if min_footer_y < page_height else 0.0

        return margin_top, margin_bottom

    # ── Очистка одной страницы ────────────────────────────────────

    @staticmethod
    def _clean_page(text: str) -> str:
        # 1. Unicode-артефакты → пробел
        text = _RE_UNICODE_JUNK.sub(" ", text)

        # 2. Номера страниц (не годы)
        text = _RE_PAGE_NUMBER.sub("", text)

        # 3. Горизонтальные разделители
        text = _RE_HORIZONTAL_RULE.sub("", text)

        # 4. Множественные пустые строки
        text = _RE_MULTIPLE_BLANK.sub("\n\n", text)

        return text.strip()

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def normalize_for_sparse(text: str) -> str:
    """Нормализует текст для sparse-поиска."""
    return " ".join(tokenize_for_sparse(text))


def tokenize_for_sparse(text: str) -> list[str]:
    """Простая токенизация для BM25."""
    return [token.lower() for token in _TOKEN_PATTERN.findall(text) if len(token) > 1]
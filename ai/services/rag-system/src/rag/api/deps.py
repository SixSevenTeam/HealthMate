"""Dependency injection helpers для FastAPI эндпоинтов.

Каждая зависимость — singleton, получаемый через get_*-функции.
FastAPI вызывает их при каждом запросе, но сами объекты создаются один раз.
"""

from __future__ import annotations

from fastapi import Depends

from rag.dialogue.service import DialogueService, get_dialogue_service


def get_dialogue_service_dep() -> DialogueService:
    """Возвращает singleton DialogueService для dependency injection."""
    return get_dialogue_service()

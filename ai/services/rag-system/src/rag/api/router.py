"""Агрегатор роутеров FastAPI для RAG-системы.

Все роутеры регистрируются здесь с общим префиксом /api/v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from rag.api.endpoints import chat, documents, medications, query

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(
    query.router,
    tags=["Консультация"],
)
api_router.include_router(
    documents.router,
    tags=["Документы"],
)

# /ai/chat + /ai/medications/validate — endpoints для Java-бэкенда (без /api/v1 префикса)
chat_router = APIRouter()
chat_router.include_router(
    chat.router,
    tags=["Java Integration"],
)
chat_router.include_router(
    medications.router,
    tags=["Java Integration"],
)

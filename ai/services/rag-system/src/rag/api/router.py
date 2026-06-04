"""Агрегатор роутеров FastAPI для RAG-системы.

Все роутеры регистрируются здесь с общим префиксом /api/v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from rag.api.endpoints import chat, documents, medications, query, tips

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(
    query.router,
    tags=["Консультация"],
)
api_router.include_router(
    documents.router,
    tags=["Документы"],
)

chat_router = APIRouter()
chat_router.include_router(
    chat.router,
    tags=["Java Integration"],
)
chat_router.include_router(
    medications.router,
    tags=["Java Integration"],
)
chat_router.include_router(
    tips.router,
    tags=["Java Integration"],
)

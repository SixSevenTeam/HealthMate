"""Агрегатор роутеров FastAPI для RAG-системы.

Все роутеры регистрируются здесь с общим префиксом /api/v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from rag.api.endpoints import documents, query

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(
    query.router,
    tags=["Консультация"],
)
api_router.include_router(
    documents.router,
    tags=["Документы"],
)

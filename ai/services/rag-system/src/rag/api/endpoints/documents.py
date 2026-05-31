"""Эндпоинты управления документами.

POST /api/v1/documents/upload — инициирует загрузку и обработку нового документа.
GET  /api/v1/documents/{document_id}/status — возвращает статус обработки.

Оба эндпоинта возвращают 501 — индексирование документов выполняется
через офлайн-пайплайн (document-parser → rag-system indexer), а не через API.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from rag.domain.events import (
    DocumentStatusResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
)

log = structlog.get_logger()

router = APIRouter()


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Загрузка документа на обработку",
    description=(
        "Принимает ссылку на документ в MinIO и инициирует его обработку: "
        "парсинг, чанкинг, embedding и сохранение в векторную БД."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(request: DocumentUploadRequest) -> DocumentUploadResponse:
    """Инициирует обработку документа."""
    log.info("upload_document_called", s3_url=request.s3_url)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Индексирование документов выполняется через офлайн-пайплайн.",
    )


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Статус обработки документа",
    description="Возвращает текущий статус обработки документа по его идентификатору.",
    status_code=status.HTTP_200_OK,
)
async def get_document_status(document_id: str) -> DocumentStatusResponse:
    """Возвращает статус обработки документа."""
    log.info("get_document_status_called", document_id=document_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Статус документов доступен только через офлайн-пайплайн.",
    )

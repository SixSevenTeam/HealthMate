"""Эндпоинты управления документами.

POST /api/v1/documents/upload — инициирует загрузку и обработку нового документа.
GET  /api/v1/documents/{document_id}/status — возвращает статус обработки.
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
    """Инициирует обработку документа.

    Args:
        request: Ссылка на файл в MinIO и метаданные документа.

    Returns:
        Идентификатор документа и статус запроса.

    Raises:
        HTTPException 500: При ошибке постановки задачи в очередь.
    """
    log.info(
        "upload_document_called",
        s3_url=request.s3_url,
    )
    # TODO:
    # 1. Сформировать DocumentParsedEvent и опубликовать в Kafka
    # 2. Вернуть document_id и статус "queued"
    log.warning("upload_document_not_implemented")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Эндпоинт загрузки документов не реализован.",
    )


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Статус обработки документа",
    description="Возвращает текущий статус обработки документа по его идентификатору.",
    status_code=status.HTTP_200_OK,
)
async def get_document_status(document_id: str) -> DocumentStatusResponse:
    """Возвращает статус обработки документа.

    Args:
        document_id: UUID документа.

    Returns:
        Текущий статус обработки.

    Raises:
        HTTPException 404: Если документ не найден.
        HTTPException 500: При внутренней ошибке.
    """
    log.info("get_document_status_called", document_id=document_id)
    # TODO:
    # 1. Запросить статус из Redis/БД по document_id
    # 2. Вернуть DocumentStatusResponse
    log.warning("get_document_status_not_implemented", document_id=document_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Эндпоинт статуса документов не реализован.",
    )

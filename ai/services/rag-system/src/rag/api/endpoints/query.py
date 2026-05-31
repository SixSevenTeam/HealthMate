"""Эндпоинт обработки медицинских запросов пользователя.

POST /api/v1/query — принимает запрос с историей диалога и профилем пользователя,
возвращает ответ текущего этапа консультации.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from rag.api.deps import get_dialogue_service_dep
from rag.dialogue.service import DialogueService
from rag.domain.events import QueryRequest, QueryResponse

log = structlog.get_logger()

router = APIRouter()


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Обработка медицинского запроса",
    description=(
        "Принимает запрос пользователя с историей диалога и профилем. "
        "Возвращает ответ текущего этапа консультации: "
        "сбор анамнеза, синтез контекста или рекомендации."
    ),
    status_code=status.HTTP_200_OK,
)
async def handle_query(
    request: QueryRequest,
    dialogue_service: DialogueService = Depends(get_dialogue_service_dep),
) -> QueryResponse:
    """Обрабатывает медицинский запрос через трёхэтапный диалог.

    Args:
        request: Запрос с историей диалога, профилем пользователя и метаданными.
        dialogue_service: Оркестратор консультации (внедряется через DI).

    Returns:
        Ответ соответствующего этапа консультации.

    Raises:
        HTTPException 422: Если тело запроса не прошло валидацию.
        HTTPException 500: При внутренней ошибке сервиса.
    """
    log.info(
        "query_endpoint_called",
        user_id=request.user_id,
        session_id=request.session_id,
    )
    try:
        response = await dialogue_service.process_query(request)
        return response
    except Exception as exc:
        log.error(
            "query_endpoint_error",
            user_id=request.user_id,
            session_id=request.session_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервиса при обработке запроса.",
        ) from exc

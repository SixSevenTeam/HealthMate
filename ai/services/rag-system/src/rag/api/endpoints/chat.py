"""Эндпоинт POST /ai/chat — точка входа для Java-бэкенда.

Java отправляет запрос пользователя сюда, Python обрабатывает через
трёхэтапный диалог и возвращает ответ с медицинским дисклеймером.
Формат запроса/ответа соответствует гайду по endpoint Васе.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from rag.api.deps import get_dialogue_service_dep
from rag.dialogue.service import DialogueService
from rag.domain.events import (
    ConversationMessage,
    QueryRequest,
    UserProfile,
)

log = structlog.get_logger()

router = APIRouter()


# ── Модели запроса/ответа по контракту Java → Python ─────────────────────────

class AiChatDiagnosis(BaseModel):
    name: str
    diagnosedAt: str | None = Field(default=None, alias="diagnosedAt")

class AiChatAllergy(BaseModel):
    allergen: str
    reaction: str | None = None

class AiChatActiveMedication(BaseModel):
    tradeName: str | None = Field(default=None, alias="tradeName")
    internationalName: str | None = Field(default=None, alias="internationalName")
    doseAmount: float | None = Field(default=None, alias="doseAmount")
    doseUnit: str | None = Field(default=None, alias="doseUnit")
    instructions: str | None = None

class AiChatUserContext(BaseModel):
    """Контекст пользователя (контракт Васе)."""
    userId: str = Field(alias="userId")
    birthDate: str | None = Field(default=None, alias="birthDate")
    heightCm: float | None = Field(default=None, alias="heightCm")
    weightKg: float | None = Field(default=None, alias="weightKg")
    bloodType: str | None = Field(default=None, alias="bloodType")
    diagnoses: list[AiChatDiagnosis] = Field(default_factory=list)
    allergies: list[AiChatAllergy] = Field(default_factory=list)
    contextDegraded: bool = Field(default=False, alias="contextDegraded")
    contextWarnings: list[str] = Field(default_factory=list, alias="contextWarnings")
    activeMedications: list[AiChatActiveMedication] = Field(default_factory=list, alias="activeMedications")
    model_config = {"populate_by_name": True}

class AiChatMessage(BaseModel):
    role: str
    content: str

class AiChatRequest(BaseModel):
    """Запрос от Java — POST /ai/chat (контракт Васе)."""
    conversationId: str = Field(alias="conversationId")
    userMessage: str = Field(alias="userMessage")
    anamnesisState: dict[str, Any] | None = Field(default=None, alias="anamnesisState")
    userContext: AiChatUserContext = Field(alias="userContext")
    conversationHistory: list[AiChatMessage] = Field(default_factory=list, alias="conversationHistory")
    model_config = {"populate_by_name": True}

class AiChatResponse(BaseModel):
    """Ответ Python → Java (контракт Васе)."""
    content: str
    messageType: str = Field(alias="messageType")
    anamnesisState: dict[str, Any] | None = Field(default=None, alias="anamnesisState")
    drugReferenceId: str | None = Field(default=None, alias="drugReferenceId")
    ragSource: str | None = Field(default=None, alias="ragSource")
    recommendedDrugs: list[dict[str, Any]] = Field(default_factory=list, alias="recommendedDrugs")
    disclaimer: str | None = None
    model_config = {"populate_by_name": True}


# ── Маппинг ──────────────────────────────────────────────────────────────────

def _to_query_request(req: AiChatRequest) -> QueryRequest:
    """Конвертирует AiChatRequest (контракт Васе) в внутренний QueryRequest."""
    from rag.domain.events import ChronicCondition, Medication

    ctx = req.userContext

    profile = UserProfile(
        allergies=[a.allergen for a in ctx.allergies],
        chronic_conditions=[
            ChronicCondition(name=d.name, diagnosed_at=d.diagnosedAt)
            for d in ctx.diagnoses
        ],
        current_medications=[
            Medication(
                name=m.tradeName or m.internationalName or "",
                dosage=f"{m.doseAmount} {m.doseUnit}" if m.doseAmount else "",
                frequency=m.instructions or "",
            )
            for m in ctx.activeMedications
        ],
    )

    history = [
        ConversationMessage(
            role=msg.role,
            content=msg.content,
            timestamp="",
        )
        for msg in req.conversationHistory
    ]

    return QueryRequest(
        user_id=ctx.userId,
        session_id=req.conversationId,
        query=req.userMessage,
        user_profile=profile,
        conversation_history=history,
    )


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post(
    "/ai/chat",
    response_model=AiChatResponse,
    summary="Медицинская консультация (Java → Python)",
    description=(
        "Принимает запрос от Java-бэкенда с сообщением пользователя, "
        "контекстом и историей. Возвращает ответ текущего этапа консультации."
    ),
    status_code=status.HTTP_200_OK,
)
async def ai_chat(
    request: AiChatRequest,
    dialogue_service: DialogueService = Depends(get_dialogue_service_dep),
) -> AiChatResponse:
    """Обрабатывает чат-запрос от Java."""
    log.info(
        "ai_chat_called",
        conversation_id=request.conversationId,
        user_id=request.userContext.userId,
    )

    try:
        query_request = _to_query_request(request)
        result = await dialogue_service.process_query(query_request)

        # Определяем messageType по response_type из DialogueService
        message_type_map = {
            "clarifying_question": "question",
            "context_summary": "info",
            "synthesis_result": "info",
            "final_recommendation": "answer",
            "medical_recommendation": "answer",
        }
        message_type = message_type_map.get(result.response_type, result.response_type)

        # Формируем anamnesisState для Java
        anamnesis_state: dict[str, Any] | None = None
        if result.stage in ("anamnesis_collection", "context_synthesis"):
            anamnesis_state = {"stage": "collecting"}
        elif result.stage == "recommendation":
            anamnesis_state = {"stage": "completed"}

        # Собираем recommendedDrugs (если есть в content)
        recommended_drugs: list[dict[str, Any]] = result.content.get("recommended_drugs", [])

        # ragSource из первого найденного документа
        rag_source: str | None = None
        if result.context_used.retrieved_documents:
            first = result.context_used.retrieved_documents[0]
            rag_source = first.document_id

        return AiChatResponse(
            content=result.content.get("message", ""),
            messageType=message_type,
            anamnesisState=anamnesis_state,
            drugReferenceId=result.content.get("drug_reference_id"),
            ragSource=rag_source,
            recommendedDrugs=recommended_drugs,
            disclaimer=result.content.get("disclaimer"),
        )

    except Exception as exc:
        log.error(
            "ai_chat_error",
            conversation_id=request.conversationId,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обработке запроса консультации.",
        ) from exc

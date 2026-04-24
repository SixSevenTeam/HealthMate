"""Доменные модели (events и DTO) RAG-системы.

Соответствуют контрактам из AI_CONTRACTS.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Событие от document-parser ────────────────────────────────────────────────

class DocumentMetadata(BaseModel):
    """Метаданные распарсенного документа."""

    title: str
    category: str
    language: str
    source_filename: str
    page_count: int
    parsed_at: datetime
    parser_version: str


class DocumentStructure(BaseModel):
    """Описание структуры JSON-дерева документа."""

    type: str = Field(..., description="Тип структуры: hierarchical | flat")
    format: str = Field(..., description="Формат: tree_json")
    root_sections: list[str] = Field(default_factory=list)
    total_nodes: int
    max_depth: int


class DocumentParsedEvent(BaseModel):
    """Входящее Kafka-событие от document-parser после успешного парсинга."""

    document_id: str = Field(..., description="UUID документа")
    s3_url: str = Field(..., description="Путь к JSON-файлу в MinIO")
    metadata: DocumentMetadata
    structure: DocumentStructure

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc-uuid-123",
                "s3_url": "s3://processed-json-doc/doc-uuid-123.json",
                "metadata": {
                    "title": "Инструкция по применению Парацетамола",
                    "category": "medication",
                    "language": "ru",
                    "source_filename": "paracetamol.htm",
                    "page_count": 1,
                    "parsed_at": "2026-04-21T15:30:00Z",
                    "parser_version": "0.1.0",
                },
                "structure": {
                    "type": "hierarchical",
                    "format": "tree_json",
                    "root_sections": ["Состав", "Показания", "Противопоказания"],
                    "total_nodes": 12,
                    "max_depth": 3,
                },
            }
        }
    }


class DocumentStatusEvent(BaseModel):
    """Исходящее Kafka-событие со статусом обработки документа."""

    document_id: str
    status: str = Field(..., description="processing | embedded | partially_embedded | failed")
    details: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Сериализует событие для отправки в Kafka."""
        return self.model_dump(exclude_none=True, mode="json")


# ── Модели пользовательского профиля (для запроса от Java) ───────────────────

class ChronicCondition(BaseModel):
    """Хроническое заболевание пользователя."""

    name: str
    diagnosed_at: str | None = None
    severity: Literal["mild", "moderate", "severe"] | None = None


class Medication(BaseModel):
    """Препарат из текущего листа лечения пользователя."""

    name: str
    dosage: str
    frequency: str
    started_at: str | None = None


class UserProfile(BaseModel):
    """Медицинский профиль пользователя для контекстуализации запроса."""

    age: int | None = None
    gender: Literal["male", "female", "other", "prefer_not_to_say"] | None = None
    allergies: list[str] = Field(default_factory=list)
    chronic_conditions: list[ChronicCondition] = Field(default_factory=list)
    current_medications: list[Medication] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    """Одно сообщение в истории диалога."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    metadata: dict[str, Any] | None = None


class QueryMetadata(BaseModel):
    """Метаданные запроса пользователя."""

    language: str = "ru"
    timezone: str | None = None
    client_version: str | None = None


# ── Запрос от Java-бэкенда ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Входящий REST-запрос на консультацию от Java-бэкенда."""

    user_id: str
    session_id: str
    query: str
    user_profile: UserProfile
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    metadata: QueryMetadata = Field(default_factory=QueryMetadata)


# ── Ответ RAG-системы ─────────────────────────────────────────────────────────

class RetrievedDocument(BaseModel):
    """Документ, найденный в векторной базе при поиске."""

    document_id: str
    chunk_id: str | None = None
    title: str | None = None
    relevance_score: float
    snippet: str | None = None


class ContextUsed(BaseModel):
    """Контекст, использованный при формировании ответа."""

    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    user_constraints_applied: list[str] = Field(default_factory=list)
    safety_checks_performed: list[str] = Field(default_factory=list)


class ResponseMetadata(BaseModel):
    """Метаданные ответа для мониторинга и отладки."""

    processing_time_ms: int | None = None
    llm_model: str | None = None
    llm_tokens_used: int | None = None
    confidence_score: float | None = None
    questions_asked: int | None = None
    max_questions: int = 3


class QueryResponse(BaseModel):
    """Исходящий ответ RAG-системы на запрос пользователя."""

    request_id: str
    session_id: str
    stage: Literal["anamnesis_collection", "context_synthesis", "recommendation"]
    response_type: str
    content: dict[str, Any]
    context_used: ContextUsed = Field(default_factory=ContextUsed)
    next_action: str
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


# ── Модели для REST /documents ────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    """Запрос на загрузку нового документа в систему."""

    document_id: str
    s3_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    """Ответ на запрос загрузки документа."""

    document_id: str
    status: str = "queued"
    estimated_processing_time_seconds: int = 30
    message: str = "Document queued for processing"


class DocumentStatusResponse(BaseModel):
    """Статус обработки документа по его ID."""

    document_id: str
    status: str
    progress: dict[str, Any] | None = None
    timestamps: dict[str, str] | None = None

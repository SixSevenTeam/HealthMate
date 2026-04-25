from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

"""Доменные модели сервиса document-parser.

Описывают контракты входящих/исходящих Kafka-событий и внутренних сущностей.
CamelCase-алиасы используются для совместимости с wire-форматом Java-бэкенда, поотму что питон явно люди делали, формат
asdASD - не правильно, все их целовал
"""

"""Входящее Kafka-событие от Java-бэкенда со ссылкой на файл в MinIO."""

class IncomingEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    minio_bucket: str = Field(..., alias="minIoBucket")
    file_path: str = Field(..., alias="filePath")


"""Внутренняя модель обработанного документа, сохраняемая в MinIO как JSON."""
class ProcessedDocument(BaseModel):

    document_id: str
    source_file: str
    tree: dict[str, Any] = Field(
        ...,
        description="Иерархическое дерево документа с заголовками и контентом",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    """Сериализует модель в dict, пригодный для JSON-сохранения."""
    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


"""Исходящее Kafka-событие с указанием результата обработки в MinIO."""
class OutgoingEvent(BaseModel):

    document_id: str
    result_bucket: str
    result_file: str
    status: str = "processed"

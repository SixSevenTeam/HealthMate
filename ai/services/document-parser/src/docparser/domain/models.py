from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from pydantic import BaseModel, Field

class IncomingEvent(BaseModel):

    id: str
    minIoBucket: str = Field(..., alias="minIoBucket")
    filePath: str

    model_config = {"populate_by_name": True}


class PageChunkModel(BaseModel):
    page: int
    text: str


class ProcessedDocument(BaseModel):
    document_id: str
    source_file: str
    tree: dict[str, Any] = Field(..., description="Дерево документа с заголовками и контекстом")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class OutgoingEvent(BaseModel):
    document_id: str
    result_bucket: str
    result_file: str
    status: str = "processed"
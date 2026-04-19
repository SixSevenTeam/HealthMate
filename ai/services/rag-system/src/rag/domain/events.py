"""Domain events - аналог Java DTO."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class DocumentParsedEvent(BaseModel):

    document_id: str = Field(..., description="UUID документа")
    s3_url: str = Field(..., description="Путь к JSON в MinIO")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc-uuid-123",
                "s3_url": "s3://processed-json-doc/doc-uuid-123.json",
                "metadata": {
                    "title": "Парацетамол инструкция",
                    "category": "medication"
                }
            }
        }


class DocumentStatusEvent(BaseModel):
    document_id: str
    status: str = Field(..., description="embedded | failed | processing")
    details: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)
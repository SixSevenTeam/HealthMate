"""Юнит-тесты для Pydantic-моделей домена."""

import json

import pytest
from pydantic import ValidationError

from docparser.domain import IncomingEvent, OutgoingEvent, ProcessedDocument


# ── IncomingEvent ──────────────────────────────────────────────────────────────

def test_incoming_event_alias_deserialization(sample_incoming_event_dict):
    """Модель должна десериализоваться из camelCase wire-формата."""
    event = IncomingEvent.model_validate(sample_incoming_event_dict)
    assert event.id == "doc-test-123"


def test_incoming_event_snake_case_attribute_access(sample_incoming_event_dict):
    """После десериализации должны работать snake_case атрибуты Python."""
    event = IncomingEvent.model_validate(sample_incoming_event_dict)
    assert event.minio_bucket == "raw-documents"
    assert event.file_path == "paracetamol.htm"


def test_incoming_event_missing_id_raises_validation_error():
    """Отсутствие обязательного поля id должно вызвать ValidationError."""
    with pytest.raises(ValidationError):
        IncomingEvent.model_validate({"minIoBucket": "bucket", "filePath": "file.htm"})


def test_incoming_event_missing_minio_bucket_raises():
    """Отсутствие minIoBucket должно вызвать ValidationError."""
    with pytest.raises(ValidationError):
        IncomingEvent.model_validate({"id": "123", "filePath": "file.htm"})


# ── ProcessedDocument ─────────────────────────────────────────────────────────

def test_processed_document_processed_at_utc():
    """processed_at должен иметь UTC-таймзону по умолчанию."""
    doc = ProcessedDocument(
        document_id="doc-1",
        source_file="file.htm",
        tree={"type": "root"},
    )
    assert doc.processed_at.tzinfo is not None


def test_processed_document_tree_accepts_any_dict():
    """Поле tree принимает произвольную вложенную структуру."""
    tree = {"type": "root", "children": [{"type": "section", "nested": {"deep": True}}]}
    doc = ProcessedDocument(document_id="doc-1", source_file="f.htm", tree=tree)
    assert doc.tree == tree


def test_processed_document_json_serializable():
    """to_storage_dict() должен возвращать JSON-сериализуемый словарь."""
    doc = ProcessedDocument(
        document_id="doc-1",
        source_file="file.htm",
        tree={"type": "root", "children": []},
    )
    data = doc.to_storage_dict()
    # Не должно вызывать исключение
    json_str = json.dumps(data)
    assert "doc-1" in json_str


# ── OutgoingEvent ─────────────────────────────────────────────────────────────

def test_outgoing_event_default_status_is_processed():
    """Статус по умолчанию должен быть 'processed'."""
    event = OutgoingEvent(
        document_id="doc-1",
        result_bucket="bucket",
        result_file="doc-1.json",
    )
    assert event.status == "processed"


def test_outgoing_event_model_dump_all_fields():
    """model_dump() должен содержать все обязательные поля."""
    event = OutgoingEvent(
        document_id="doc-1",
        result_bucket="bucket",
        result_file="doc-1.json",
    )
    data = event.model_dump()
    assert "document_id" in data
    assert "result_bucket" in data
    assert "result_file" in data
    assert "status" in data

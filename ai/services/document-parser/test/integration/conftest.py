from unittest.mock import AsyncMock, MagicMock

import pytest

from docparser.domain import IncomingEvent, OutgoingEvent


@pytest.fixture
def mock_storage():
    """AsyncMock для MinioStorage с реалистичными возвращаемыми значениями."""
    storage = AsyncMock()
    storage.object_exists = AsyncMock(return_value=False)
    storage.download_file = AsyncMock(return_value=None)
    storage.upload_json = AsyncMock(return_value=None)
    return storage


@pytest.fixture
def mock_producer():
    """AsyncMock для KafkaEventProducer."""
    producer = AsyncMock()
    producer.send_status = AsyncMock(return_value=None)
    producer.send_event = AsyncMock(return_value=None)
    return producer


@pytest.fixture
def mock_processor():
    """MagicMock для Processor — возвращает один Markdown-чанк."""
    processor = MagicMock()
    processor.convert_to_markdown = MagicMock(
        return_value=[{"page": 1, "text": "# Парацетамол\n\nОбезболивающее средство."}]
    )
    return processor


@pytest.fixture
def mock_tree_builder():
    """MagicMock для MarkdownTreeBuilder — возвращает минимальное дерево."""
    tree_builder = MagicMock()
    tree_builder.build_tree = MagicMock(
        return_value={
            "type": "root",
            "heading": {"depth": 0, "title": "Document Root", "page_starts_at": 1},
            "content": "",
            "children": [
                {
                    "type": "section",
                    "heading": {"depth": 1, "title": "Парацетамол", "page_starts_at": 1},
                    "content": "Обезболивающее средство.",
                    "children": [],
                }
            ],
        }
    )
    return tree_builder


@pytest.fixture
def sample_event() -> IncomingEvent:
    """Валидное входящее событие в wire-формате."""
    return IncomingEvent.model_validate(
        {
            "id": "doc-integration-test",
            "minIoBucket": "raw-documents",
            "filePath": "paracetamol.htm",
        }
    )

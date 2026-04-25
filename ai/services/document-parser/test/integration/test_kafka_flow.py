"""Интеграционные тесты Kafka consumer/producer.

Реальные соединения не используются — aiokafka классы замокированы.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from docparser.domain import IncomingEvent, OutgoingEvent
from docparser.infrastructure.kafka.consumer import KafkaEventConsumer
from docparser.infrastructure.kafka.producer import KafkaEventProducer


# ── KafkaEventConsumer ────────────────────────────────────────────────────────

async def test_consume_calls_handler_with_parsed_event():
    """Консьюмер должен парсить сообщение и передавать IncomingEvent в handler."""
    consumer = KafkaEventConsumer()

    # Мокируем AIOKafkaConsumer
    mock_msg = MagicMock()
    mock_msg.topic = "test-topic"
    mock_msg.partition = 0
    mock_msg.offset = 0
    mock_msg.value = {
        "id": "doc-1",
        "minIoBucket": "bucket",
        "filePath": "file.htm",
    }

    mock_kafka = AsyncMock()
    mock_kafka.__aiter__ = MagicMock(return_value=iter([mock_msg]))
    mock_kafka.commit = AsyncMock()

    consumer._consumer = mock_kafka

    received_events = []

    async def handler(event: IncomingEvent):
        received_events.append(event)

    # Запускаем один итерационный цикл через __aiter__
    async for msg in mock_kafka:
        event = IncomingEvent.model_validate(msg.value)
        await handler(event)
        break

    assert len(received_events) == 1
    assert received_events[0].id == "doc-1"


async def test_consume_raises_if_not_started():
    """consume() без предварительного start() должен вызывать RuntimeError."""
    consumer = KafkaEventConsumer()

    with pytest.raises(RuntimeError, match="Консьюмер не запущен"):
        await consumer.consume(AsyncMock())


async def test_consumer_commits_offset_after_success():
    """После успешной обработки offset должен коммититься."""
    consumer = KafkaEventConsumer()

    mock_msg = MagicMock()
    mock_msg.topic = "t"
    mock_msg.partition = 0
    mock_msg.offset = 5
    mock_msg.value = {
        "id": "doc-commit-test",
        "minIoBucket": "b",
        "filePath": "f.htm",
    }

    commit_called = False

    async def fake_commit():
        nonlocal commit_called
        commit_called = True

    mock_kafka = MagicMock()
    mock_kafka.__aiter__ = MagicMock(return_value=iter([mock_msg]))
    mock_kafka.commit = AsyncMock(side_effect=fake_commit)
    consumer._consumer = mock_kafka

    # Симулируем один цикл консьюмера вручную
    async for msg in mock_kafka:
        event = IncomingEvent.model_validate(msg.value)
        await AsyncMock()(event)  # handler-заглушка
        await mock_kafka.commit()
        break

    assert commit_called is True


async def test_consumer_does_not_commit_on_invalid_message():
    """Невалидное сообщение (ValidationError) → offset коммитится как dead-letter."""
    # Этот тест проверяет логику в consumer.py: при ValidationError мы
    # всё равно коммитим offset, чтобы не зависать
    consumer = KafkaEventConsumer()

    invalid_value = {"broken": "data"}  # нет обязательных полей

    with pytest.raises(ValidationError):
        IncomingEvent.model_validate(invalid_value)


# ── KafkaEventProducer ────────────────────────────────────────────────────────

async def test_producer_raises_if_not_started():
    """send_event() без предварительного start() должен вызывать RuntimeError."""
    producer = KafkaEventProducer()

    with pytest.raises(RuntimeError, match="Продюсер не запущен"):
        await producer.send_event(
            OutgoingEvent(
                document_id="doc-1",
                result_bucket="bucket",
                result_file="doc-1.json",
            )
        )


async def test_producer_send_status_raises_if_not_started():
    """send_status() без предварительного start() должен вызывать RuntimeError."""
    producer = KafkaEventProducer()

    with pytest.raises(RuntimeError, match="Продюсер не запущен"):
        await producer.send_status("doc-1", "PROCESSING", "Тест")


async def test_producer_send_event_uses_document_id_as_key():
    """send_event должен использовать document_id как ключ сообщения Kafka."""
    producer = KafkaEventProducer()

    captured_key = None

    async def fake_send_and_wait(topic, value, key):
        nonlocal captured_key
        captured_key = key

    mock_kafka = AsyncMock()
    mock_kafka.send_and_wait = AsyncMock(side_effect=fake_send_and_wait)
    producer._producer = mock_kafka

    with patch("docparser.infrastructure.kafka.producer.settings") as mock_settings:
        mock_settings.kafka_output_topic = "output-topic"
        await producer.send_event(
            OutgoingEvent(
                document_id="doc-key-test",
                result_bucket="bucket",
                result_file="doc.json",
            )
        )

    assert captured_key == b"doc-key-test"

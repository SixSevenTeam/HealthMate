from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from aiokafka import AIOKafkaProducer

from docparser.core import settings
from docparser.domain import OutgoingEvent

log = structlog.get_logger()

"""Kafka-продюсер на базе aiokafka.

Отправляет два типа событий:
1. send_event — итоговое событие (OutgoingEvent) для RAG-сервиса
2. send_status — статусные обновления (PROCESSING / MARKDOWN_READY / FAILED)
   для Java-бэкенда и SSE-потока пользователя
"""
"""Продюсер Kafka-событий сервиса document-parser."""
class KafkaEventProducer:

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    """Инициализирует и запускает Kafka-продюсер."""
    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            acks="all",
        )
        await self._producer.start()
        log.info("kafka_producer_started")

    """Graceful shutdown продюсера."""
    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            log.info("kafka_producer_stopped")

    """Отправляет итоговое событие в topic для RAG-сервиса.

        Args:
            event: Данные об обработанном документе.

        Raises:
            RuntimeError: Если продюсер не был запущен через start().
        """
    async def send_event(self, event: OutgoingEvent) -> None:
        if not self._producer:
            raise RuntimeError("Продюсер не запущен — вызовите start() сначала")

        payload = event.model_dump()

        log.debug(
            "kafka_send_event",
            topic=settings.kafka_output_topic,
            document_id=event.document_id,
        )

        await self._producer.send_and_wait(
            settings.kafka_output_topic,
            value=payload,
            key=event.document_id.encode("utf-8"),
        )

        log.info(
            "kafka_event_sent",
            topic=settings.kafka_output_topic,
            document_id=event.document_id,
        )

    """Отправляет статусное событие в topic мониторинга.

        Args:
            document_id: Идентификатор документа.
            status: Статус обработки (PROCESSING / MARKDOWN_READY / FAILED).
            message: Текстовое описание текущего шага или ошибки.

        Raises:
            RuntimeError: Если продюсер не был запущен через start().
        """
    async def send_status(self, document_id: str, status: str, message: str) -> None:
        if not self._producer:
            raise RuntimeError("Продюсер не запущен — вызовите start() сначала")

        payload = {
            "document_id": document_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log.debug(
            "kafka_send_status",
            topic=settings.kafka_status_topic,
            document_id=document_id,
            status=status,
        )

        await self._producer.send_and_wait(
            settings.kafka_status_topic,
            key=document_id.encode("utf-8"),
            value=payload,
        )

        log.info(
            "kafka_status_sent",
            topic=settings.kafka_status_topic,
            document_id=document_id,
            status=status,
        )

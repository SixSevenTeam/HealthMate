"""Kafka consumer на базе aiokafka.

Реализует At-Least-Once семантику:
- auto_commit выключен
- offset коммитится только ПОСЛЕ успешной обработки сообщения
- при падении — сообщение будет прочитано повторно (idempotency
  обеспечивается на уровне application service)
"""

import json
from typing import Callable, Awaitable

import structlog
from aiokafka import AIOKafkaConsumer

from docparser.core.config import settings
from docparser.domain.models import IncomingEvent

logger = structlog.get_logger()


class KafkaEventConsumer:
    """Потребитель Kafka-сообщений с PDF-событиями."""

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.kafka_input_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self._consumer.start()
        logger.info(
            "kafka_consumer_started",
            topic=settings.kafka_input_topic,
            group=settings.kafka_consumer_group,
        )

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            logger.info("kafka_consumer_stopped")

    async def consume(
        self,
        handler: Callable[[IncomingEvent], Awaitable[None]],
    ) -> None:
        """Бесконечный цикл чтения сообщений.

        """
        if not self._consumer:
            raise RuntimeError("Consumer not started — call start() first")

        async for msg in self._consumer:
            log = logger.bind(
                topic=msg.topic,
                partition=msg.partition,
                offset=msg.offset,
            )
            try:
                event = IncomingEvent(**msg.value)
                log.info("kafka_message_received", document_id=event.id)
                await handler(event)
                await self._consumer.commit()
                log.info("kafka_offset_committed", document_id=event.id)
            except Exception:
                log.exception("kafka_message_processing_error")
                # Offset НЕ коммитится — при рестарте сообщение будет //todo сделать, чтобы сообщения коммитились??
                # прочитано повторно (At-Least-Once).
                raise

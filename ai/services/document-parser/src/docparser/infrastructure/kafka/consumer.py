
from __future__ import annotations

import json
from typing import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from docparser.core import settings
from docparser.domain import IncomingEvent

log = structlog.get_logger()

"""Kafka-консьюмер на базе aiokafka.

Реализует At-Least-Once семантику:
- auto_commit выключен
- offset коммитится только ПОСЛЕ успешной обработки сообщения
- ошибки десериализации (плохой JSON / невалидный контракт) коммитятся
  как dead-letter, чтобы не застрять на одном сообщении навсегда
- ошибки обработчика — offset НЕ коммитится, сообщение будет прочитано
  повторно при рестарте (idempotency обеспечивается на уровне сервиса)
"""
"""Потребитель Kafka-сообщений с событиями документов."""
class KafkaEventConsumer:

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None

    """Инициализирует и запускает Kafka-консьюмер."""
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
        log.info(
            "kafka_consumer_started",
            topic=settings.kafka_input_topic,
            group=settings.kafka_consumer_group,
        )

    """Graceful shutdown консьюмера."""
    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            log.info("kafka_consumer_stopped")

    """Бесконечный цикл чтения сообщений из Kafka.

        Args:
            handler: Async-функция обработки одного события.

        Raises:
            RuntimeError: Если консьюмер не был запущен через start().
        """
    async def consume(
            self,
            handler: Callable[[IncomingEvent], Awaitable[None]],
    ) -> None:
        if not self._consumer:
            raise RuntimeError("Консьюмер не запущен — вызовите start() сначала")

        async for msg in self._consumer:
            bound_log = log.bind(
                topic=msg.topic,
                partition=msg.partition,
                offset=msg.offset,
            )
            bound_log.debug("kafka_message_received")

            try:
                event = IncomingEvent.model_validate(msg.value)
            except (ValidationError, KeyError, TypeError) as exc:
                bound_log.warning(
                    "kafka_message_invalid",
                    error=str(exc),
                    raw_value=repr(msg.value)[:200],
                )
                await self._consumer.commit()
                continue

            bound_log = bound_log.bind(document_id=event.id)
            bound_log.info("kafka_event_parsed", document_id=event.id)

            try:
                await handler(event)
                await self._consumer.commit()
                bound_log.info("kafka_offset_committed", document_id=event.id)
            except Exception:
                bound_log.exception("kafka_handler_failed")
                raise

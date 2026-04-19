import json
from datetime import datetime, timezone

import structlog
from aiokafka import AIOKafkaProducer

from docparser.core.config import settings
from docparser.domain.models import OutgoingEvent

logger = structlog.get_logger()


class KafkaEventProducer:
    """Отправитель Kafka-событий."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            acks="all",  # ждём подтверждения от всех ISR-реплик
        )
        await self._producer.start()
        logger.info("kafka_producer_started")

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("kafka_producer_stopped")

    async def send_event(self, event: OutgoingEvent) -> None:
        """Отправляет исходящее событие в output-topic."""
        if not self._producer:
            raise RuntimeError("Producer not started — call start() first")

        payload = event.model_dump()
        await self._producer.send_and_wait(
            settings.kafka_output_topic,
            value=payload,
            key=event.document_id.encode("utf-8"),
        )
        logger.info(
            "kafka_event_sent",
            topic=settings.kafka_output_topic,
            document_id=event.document_id,
        )

    async def send_status(self, document_id: str, status: str, message: str) -> None:
        if not self._producer:
            raise RuntimeError("Producer not started — call start() first")

        payload = {
            "document_id": document_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        topic = getattr(settings, "kafka_status_topic", "document-status-updates")

        await self._producer.send_and_wait(
            topic,
            key=document_id.encode("utf-8"),
            value=payload,
        )
        logger.info(
            "kafka_status_sent",
            topic=topic,
            document_id=document_id,
            status=status,
        )
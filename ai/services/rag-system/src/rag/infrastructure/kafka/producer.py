import json
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
import structlog

from rag.core.config import settings
from rag.domain.events import DocumentStatusEvent

logger = structlog.get_logger()


class StatusProducer:

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def start(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        )
        await self._producer.start()
        logger.info("kafka_producer_started")

    async def send_status(
            self,
            document_id: str,
            status: str,
            details: dict | None = None,
            error: dict | None = None,
    ):
        """
        Отправляет статус обработки документа.

        Args:
            document_id: ID документа
            status: "embedded" | "failed" | "processing"
            details: Детали (chunk_count, etc)
            error: Информация об ошибке
        """
        if not self._producer:
            raise RuntimeError("Producer not started")

        event = DocumentStatusEvent(
            document_id=document_id,
            status=status,
            details=details,
            error=error,
        )

        await self._producer.send_and_wait(
            settings.kafka_status_topic,
            key=document_id.encode("utf-8"),
            value=event.to_dict(),
        )

        logger.info(
            "status_sent",
            document_id=document_id,
            status=status,
        )

    async def stop(self):
        if self._producer:
            await self._producer.stop()
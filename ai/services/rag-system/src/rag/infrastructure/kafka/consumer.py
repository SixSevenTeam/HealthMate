"""Kafka consumer для RAG system."""

import json

from aiokafka import AIOKafkaConsumer
import structlog

from rag.core.config import settings
from rag.application.document_processor import DocumentProcessor

logger = structlog.get_logger()


class DocumentEmbeddingConsumer:
    def __init__(self):
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            settings.kafka_input_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self._consumer.start()
        logger.info("kafka_consumer_started", topic=settings.kafka_input_topic)

    async def consume_loop(self):
        processor = DocumentProcessor()

        async for msg in self._consumer:
            try:
                event = msg.value

                await processor.process_document(event)

                await self._consumer.commit()

            except Exception as e:
                logger.error(
                    "event_processing_failed",
                    error=str(e),
                    offset=msg.offset,
                )

    async def stop(self):
        if self._consumer:
            await self._consumer.stop()
            logger.info("kafka_consumer_stopped")
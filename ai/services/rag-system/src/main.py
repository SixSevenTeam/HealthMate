"""Entry point для RAG system."""

import asyncio
import signal

import structlog

from rag.core.config import settings
from rag.core.logger import setup_logging
from rag.application.document_processor import DocumentProcessor
from rag.infrastructure.kafka.consumer import DocumentEmbeddingConsumer
from rag.infrastructure.kafka.producer import StatusProducer

setup_logging()
logger = structlog.get_logger()


async def main() -> None:
    """Инициализация и запуск RAG system consumer."""

    logger.info(
        "service_starting",
        service=settings.service_name,
        version=settings.service_version,
        kafka=settings.kafka_bootstrap_servers,
        input_topic=settings.kafka_input_topic,
        output_topic=settings.kafka_status_topic,
        qdrant=settings.qdrant_url,
        minio=settings.minio_endpoint,
    )

    # ── Инфраструктурные компоненты ───────────────────────────────
    processor = DocumentProcessor()
    consumer = DocumentEmbeddingConsumer()

    # ── Graceful shutdown ─────────────────────────────────────────
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        shutdown_event.set()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    except NotImplementedError:
        # Windows не поддерживает add_signal_handler
        pass

    # ── Запуск ────────────────────────────────────────────────────
    await consumer.start()

    # Инициализируем producer внутри processor при первом использовании
    # (см. _ensure_producer_started в DocumentProcessor)

    logger.info("service_started")

    # Запускаем consumer loop
    consumer_task = asyncio.create_task(
        consumer.consume_loop()
    )
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        {consumer_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # ── Остановка ─────────────────────────────────────────────────
    for task in pending:
        task.cancel()

    await consumer.stop()

    # Останавливаем producer если был запущен
    if processor.status_producer._producer:
        await processor.status_producer.stop()

    logger.info("service_stopped")


if __name__ == "__main__":
    asyncio.run(main())
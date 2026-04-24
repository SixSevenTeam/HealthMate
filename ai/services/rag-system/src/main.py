"""Entry point для RAG system.

Запускает два параллельных компонента:
- FastAPI HTTP-сервер (uvicorn) — принимает запросы от Java-бэкенда.
- Kafka consumer — обрабатывает события document.parsed от document-parser.
"""

from __future__ import annotations

import asyncio
import signal

import structlog
import uvicorn
from fastapi import FastAPI

from rag.api.router import api_router
from rag.application.document_processor import DocumentProcessor
from rag.core.config import settings
from rag.core.logger import setup_logging
from rag.infrastructure.kafka.consumer import DocumentEmbeddingConsumer

setup_logging()
logger = structlog.get_logger()

# ── FastAPI приложение ────────────────────────────────────────────────────────

app = FastAPI(
    title="HealthMate RAG System",
    version=settings.service_version,
    description=(
        "RAG-система для медицинской консультации: "
        "обработка документов, диалоговый интерфейс, векторный поиск."
    ),
)

app.include_router(api_router)


@app.get("/health", tags=["Служебные"])
async def health_check() -> dict[str, str]:
    """Проверка доступности сервиса."""
    return {"status": "ok", "service": settings.service_name}


# ── Kafka consumer loop ───────────────────────────────────────────────────────

async def _run_kafka_consumer(shutdown_event: asyncio.Event) -> None:
    """Запускает Kafka consumer и останавливает его по сигналу shutdown."""
    processor = DocumentProcessor()
    consumer = DocumentEmbeddingConsumer()

    await consumer.start()
    logger.info("kafka_consumer_started")

    consumer_task = asyncio.create_task(consumer.consume_loop())
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        {consumer_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()

    await consumer.stop()

    if processor.status_producer._producer:
        await processor.status_producer.stop()

    logger.info("kafka_consumer_stopped")


# ── Главная точка входа ───────────────────────────────────────────────────────

async def main() -> None:
    """Инициализация и параллельный запуск HTTP-сервера и Kafka consumer."""
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

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        shutdown_event.set()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    except NotImplementedError:
        # Windows не поддерживает add_signal_handler
        pass

    # Uvicorn config — не блокирует event loop
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",  # structlog обеспечивает своё логирование
        loop="none",          # используем уже запущенный asyncio loop
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    logger.info("service_started", http_port=8000)

    # Запускаем HTTP-сервер и Kafka consumer параллельно
    await asyncio.gather(
        uvicorn_server.serve(),
        _run_kafka_consumer(shutdown_event),
    )

    logger.info("service_stopped")


if __name__ == "__main__":
    asyncio.run(main())

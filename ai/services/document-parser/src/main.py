import asyncio
import signal

import structlog

from docparser.application import DocumentProcessingService
from docparser.core import settings
from docparser.core.logger import setup_logging
from docparser.infrastructure.kafka.consumer import KafkaEventConsumer
from docparser.infrastructure.kafka.producer import KafkaEventProducer
from docparser.infrastructure.minio import MinioStorage
from docparser.infrastructure.pars import Processor
from docparser.infrastructure.pars.tree_builder import MarkdownTreeBuilder

setup_logging()
log = structlog.get_logger()


async def main() -> None:
    log.info(
        "service_starting",
        kafka=settings.kafka_bootstrap_servers,
        minio=settings.minio_endpoint,
        input_topic=settings.kafka_input_topic,
        output_topic=settings.kafka_output_topic,
    )


    storage = MinioStorage()
    processor = Processor()
    tree_builder = MarkdownTreeBuilder()
    producer = KafkaEventProducer()
    consumer = KafkaEventConsumer()

    service = DocumentProcessingService(storage, processor, tree_builder, producer)


    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        log.info("shutdown_signal_received")
        shutdown_event.set()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    except NotImplementedError:
        pass

    try:
        await producer.start()
        await consumer.start()
    except Exception as exc:
        log.error("service_startup_failed", error=str(exc))
        await producer.stop()
        raise

    log.info("service_started")

    consumer_task = asyncio.create_task(consumer.consume(service.process_event))
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        {consumer_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()

    await consumer.stop()
    await producer.stop()
    log.info("service_stopped")


if __name__ == "__main__":
    asyncio.run(main())

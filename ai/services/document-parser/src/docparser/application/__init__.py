from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from minio.error import S3Error

from docparser.core import settings
from docparser.domain import IncomingEvent, OutgoingEvent, ProcessedDocument
from docparser.infrastructure.kafka.producer import KafkaEventProducer
from docparser.infrastructure.minio import MinioStorage
from docparser.infrastructure.pars import Processor
from docparser.infrastructure.pars.tree_builder import MarkdownTreeBuilder

log = structlog.get_logger()

"""Сервис обработки HTM-документов (Application layer).

    Оркестрирует полный pipeline: MinIO -> Processor -> TreeBuilder -> MinIO -> Kafka.
    """
class DocumentProcessingService:


    def __init__(
        self,
        storage: MinioStorage,
        processor: Processor,
        tree_builder: MarkdownTreeBuilder,
        producer: KafkaEventProducer,
    ) -> None:
        self._storage = storage
        self._processor = processor
        self._tree_builder = tree_builder
        self._producer = producer


    """Полный pipeline обработки одного входящего события.

            Args:
                event: Входящее Kafka-событие с ссылкой на файл в MinIO.
            """
    async def process_event(self, event: IncomingEvent) -> None:

        bound_log = log.bind(document_id=event.id)
        output_bucket = settings.minio_output_bucket
        output_object = f"{event.id}.json"

        # проверяем, не обработан ли уже
        bound_log.debug("idempotency_check", output_object=output_object)
        already_exists = await self._storage.object_exists(output_bucket, output_object)

        if already_exists:
            bound_log.info(
                "document_already_processed",
                result=f"minio://{output_bucket}/{output_object}",
            )
            await self._producer.send_status(
                event.id, "MARKDOWN_READY", "Документ уже был обработан ранее"
            )
            out_event = OutgoingEvent(
                document_id=event.id,
                result_bucket=output_bucket,
                result_file=output_object,
                status="processed",
            )
            await self._producer.send_event(out_event)
            return

        # Скачиваем файл из MinIO
        await self._producer.send_status(
            event.id, "PROCESSING", "Скачивание файла из хранилища..."
        )

        bucket, object_name = self._parse_minio_path(
            event.file_path, event.minio_bucket
        )
        bound_log.debug("minio_path_resolved", bucket=bucket, object_name=object_name)

        temp_dir = Path(settings.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_file = str(temp_dir / f"{event.id}.htm")

        try:
            try:
                await self._storage.download_file(bucket, object_name, local_file)
            except S3Error as exc:
                if exc.code == "NoSuchKey":
                    bound_log.warning(
                        "file_not_found_in_minio",
                        bucket=bucket,
                        object_name=object_name,
                    )
                    await self._producer.send_status(
                        event.id, "FAILED", f"Файл не найден в хранилище: {object_name}"
                    )
                    return
                raise

            # 3. HTM -> очищенный Markdown (по страницам)
            await self._producer.send_status(
                event.id, "PROCESSING", "Парсинг HTM-документа в Markdown..."
            )

            page_chunks = await asyncio.to_thread(
                self._processor.convert_to_markdown, local_file
            )
            bound_log.debug("markdown_conversion_done", chunks=len(page_chunks))

            await self._producer.send_status(
                event.id, "PROCESSING", "Документ сконвертирован в Markdown, строится дерево..."
            )

            # 4. Markdown -> иерархическое дерево JSON
            tree_data = await asyncio.to_thread(
                self._tree_builder.build_tree, page_chunks
            )

            # 5. Формируем JSON-документ и загружаем в MinIO
            await self._producer.send_status(
                event.id, "PROCESSING", "Сохранение результата..."
            )
            doc = ProcessedDocument(
                document_id=event.id,
                source_file=event.file_path,
                tree=tree_data,
            )
            await self._storage.upload_json(output_bucket, output_object, doc.to_storage_dict())

            # 6. Отправляем Kafka-события
            await self._producer.send_status(
                event.id,
                "MARKDOWN_READY",
                "Документ успешно обработан и сохранён",
            )
            out_event = OutgoingEvent(
                document_id=event.id,
                result_bucket=output_bucket,
                result_file=output_object,
                status="processed",
            )
            await self._producer.send_event(out_event)

            bound_log.info(
                "document_processed_ok",
                result=f"minio://{output_bucket}/{output_object}",
            )

        except Exception as exc:
            # Offset НЕ коммитится на уровне консьюмера — сообщение
            # будет перечитано при рестарте (At-Least-Once семантика)
            bound_log.error(
                "document_processing_failed",
                error=str(exc),
                exc_info=True,
            )
            await self._producer.send_status(
                event.id, "FAILED", f"Внутренняя ошибка обработки: {exc}"
            )

        finally:
            self._cleanup(local_file)

    # Вспомогательные методы
    """Разбирает путь файла в MinIO на (bucket, object_name).

            Поддерживает форматы:
            - minio://bucket/path/to/file.htm
            - bucket/path/to/file.htm
            - path/to/file.htm  (bucket берётся из fallback_bucket)

            Args:
                file_path: Путь из события.
                fallback_bucket: Корзина по умолчанию.
            """
    @staticmethod
    def _parse_minio_path(
        file_path: str,
        fallback_bucket: str,
    ) -> tuple[str, str]:

        prefix = "minio://"
        if file_path.startswith(prefix):
            rest = file_path[len(prefix):]
            parts = rest.split("/", 1)
            if len(parts) == 2:
                log.debug("minio_path_parsed", format="minio://bucket/object")
                return parts[0], parts[1]

        if file_path.startswith(f"{fallback_bucket}/"):
            object_name = file_path[len(fallback_bucket) + 1:]
            log.debug("minio_path_parsed", format="bucket/object")
            return fallback_bucket, object_name

        log.debug("minio_path_parsed", format="bare_object")
        return fallback_bucket, file_path

    """Удаляет временный файл. Ошибки логируются, но не поднимаются."""
    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            log.warning("temp_file_cleanup_failed", path=path, error=str(exc))

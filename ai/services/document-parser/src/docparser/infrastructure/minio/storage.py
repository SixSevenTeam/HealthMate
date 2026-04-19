"""MinIO storage adapter.

Оборачивает синхронный minio SDK в async-методы через asyncio.to_thread.
Retries реализованы через tenacity — защита от краткосрочных сбоев сети/MinIO.
"""

import io
import json
import asyncio

import structlog
from minio import Minio
from minio.error import S3Error
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from docparser.core.config import settings

logger = structlog.get_logger()

# Повторяем только на S3Error и сетевые ошибки
_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((S3Error, ConnectionError, OSError)),
    reraise=True,
)


class MinioStorage:
    """Работа с объектным хранилищем MinIO."""

    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    # ── Скачивание PDF ────────────────────────────────────────────

    @retry(**_RETRY_POLICY)
    async def download_file(
            self, bucket_name: str, object_name: str, file_path: str
    ) -> None:
        """Скачивает объект из MinIO в локальный файл."""
        logger.info(
            "minio_download_start",
            bucket=bucket_name,
            object=object_name,
            dest=file_path,
        )
        await asyncio.to_thread(
            self.client.fget_object, bucket_name, object_name, file_path
        )
        logger.info("minio_download_ok", bucket=bucket_name, object=object_name)

    # ── Загрузка JSON-результата ──────────────────────────────────

    @retry(**_RETRY_POLICY)
    async def upload_json(
            self, bucket_name: str, object_name: str, data: dict
    ) -> None:
        """Сериализует dict → JSON и загружает в MinIO.

        Автоматически создаёт корзину, если её нет.
        """
        logger.info(
            "minio_upload_start", bucket=bucket_name, object=object_name
        )

        exists = await asyncio.to_thread(
            self.client.bucket_exists, bucket_name
        )
        if not exists:
            await asyncio.to_thread(self.client.make_bucket, bucket_name)
            logger.info("minio_bucket_created", bucket=bucket_name)

        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        json_stream = io.BytesIO(json_bytes)

        await asyncio.to_thread(
            self.client.put_object,
            bucket_name,
            object_name,
            json_stream,
            length=len(json_bytes),
            content_type="application/json",
        )
        logger.info("minio_upload_ok", bucket=bucket_name, object=object_name)

    # ── Проверка существования (idempotency) ──────────────────────

    async def object_exists(
            self, bucket_name: str, object_name: str
    ) -> bool:
        """Возвращает True, если объект уже есть в MinIO.

        Используется для idempotency: не обрабатываем PDF повторно,
        если результат уже сохранён.
        """
        try:
            await asyncio.to_thread(
                self.client.stat_object, bucket_name, object_name
            )
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise

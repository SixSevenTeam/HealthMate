from __future__ import annotations

import asyncio
import io
import json

import structlog
from minio import Minio
from minio.error import S3Error
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docparser.core import settings

log = structlog.get_logger()

_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((S3Error, ConnectionError, OSError)),
    reraise=True,
)

class MinioStorage:

    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )


    """Скачивает объект из MinIO в локальный файл.

        Args:
            bucket_name: Имя корзины.
            object_name: Путь к объекту в корзине.
            file_path: Локальный путь для сохранения файла.
        """
    @retry(**_RETRY_POLICY)
    async def download_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
    ) -> None:
        log.info(
            "minio_download_start",
            bucket=bucket_name,
            object=object_name,
            dest=file_path,
        )
        await asyncio.to_thread(
            self.client.fget_object, bucket_name, object_name, file_path
        )
        log.info("minio_download_ok", bucket=bucket_name, object=object_name)


    """Сериализует dict → JSON и загружает в MinIO.

        Автоматически создаёт корзину, если её нет.

        Args:
            bucket_name: Имя целевой корзины.
            object_name: Путь объекта в корзине.
            data: Данные для сериализации.
        """
    @retry(**_RETRY_POLICY)
    async def upload_json(
            self,
            bucket_name: str,
            object_name: str,
            data: dict,
    ) -> None:
        log.info("minio_upload_start", bucket=bucket_name, object=object_name)

        exists = await asyncio.to_thread(self.client.bucket_exists, bucket_name)
        if not exists:
            await asyncio.to_thread(self.client.make_bucket, bucket_name)
            log.info("minio_bucket_created", bucket=bucket_name)

        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        json_stream = io.BytesIO(json_bytes)

        await asyncio.to_thread(
            self.client.put_object,
            bucket_name,
            object_name,
            json_stream,
            length=len(json_bytes),
            content_type="application/json",
        )
        log.info("minio_upload_ok", bucket=bucket_name, object=object_name)


    """Возвращает True, если объект уже есть в MinIO.

        Используется для idempotency: не обрабатываем документ повторно,
        если результат уже сохранён в хранилище.

        Args:
            bucket_name: Имя корзины.
            object_name: Путь к объекту.

        Raises:
            S3Error: При любой ошибке, кроме «NoSuchKey».
        """
    async def object_exists(self, bucket_name: str, object_name: str) -> bool:
        log.debug("minio_check_exists", bucket=bucket_name, object=object_name)
        try:
            await asyncio.to_thread(
                self.client.stat_object, bucket_name, object_name
            )
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            log.warning(
                "minio_unexpected_s3_error",
                bucket=bucket_name,
                object=object_name,
                code=exc.code,
            )
            raise

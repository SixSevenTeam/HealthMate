"""MinIO client для скачивания JSON."""

import json
from typing import Dict, Any
from pathlib import Path

from minio import Minio
import structlog

from rag.core.config import settings

logger = structlog.get_logger()


class MinioClient:

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_input_bucket

    async def download_json(self, s3_url: str) -> Dict[str, Any]:
        """
        Скачивает JSON файл из MinIO.

        Args:
            s3_url: Путь типа
        """

        if s3_url.startswith("s3://"):
            s3_url = s3_url[5:]


        object_name = s3_url.split("/", 1)[-1]

        logger.info("downloading_from_minio", object_name=object_name)

        try:

            temp_dir = Path(settings.temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)

            temp_file = temp_dir / f"{object_name.replace('/', '_')}"

            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=object_name,
                file_path=str(temp_file),
            )


            with open(temp_file, "r", encoding="utf-8") as f:
                data = json.load(f)


            temp_file.unlink()

            logger.info("json_downloaded", object_name=object_name)
            return data

        except Exception as e:
            logger.error("minio_download_failed", error=str(e), object_name=object_name)
            raise
"""Tests for MinioClient (rag-system)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest

from rag.infrastructure.minio.storage import MinioClient


class TestMinioClient:

    @pytest.fixture
    def mock_minio(self):
        with patch("rag.infrastructure.minio.storage.Minio") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def client(self, mock_minio):
        return MinioClient()

    async def test_download_json_strips_s3_prefix(self, client, mock_minio, tmp_path):
        json_data = {"key": "value"}
        temp_file = tmp_path / "bucket_doc.json"
        temp_file.write_text(json.dumps(json_data), encoding="utf-8")

        with patch.object(client, "client") as m:
            def fake_fget(bucket_name, object_name, file_path):
                import shutil
                shutil.copy(str(temp_file), file_path)

            m.fget_object.side_effect = fake_fget

            with patch("rag.infrastructure.minio.storage.settings") as mock_cfg:
                mock_cfg.temp_dir = str(tmp_path / "tmp")
                mock_cfg.minio_input_bucket = "bucket"

                result = await client.download_json("s3://bucket/doc.json")

            assert result == json_data

    async def test_download_json_without_prefix(self, client, mock_minio, tmp_path):
        json_data = {"hello": "world"}
        temp_file = tmp_path / "raw.json"
        temp_file.write_text(json.dumps(json_data), encoding="utf-8")

        with patch.object(client, "client") as m:
            def fake_fget(bucket_name, object_name, file_path):
                import shutil
                shutil.copy(str(temp_file), file_path)

            m.fget_object.side_effect = fake_fget

            with patch("rag.infrastructure.minio.storage.settings") as mock_cfg:
                mock_cfg.temp_dir = str(tmp_path / "tmp2")
                mock_cfg.minio_input_bucket = "bucket"

                result = await client.download_json("bucket/raw.json")

            assert result == json_data

    async def test_download_json_error_raises(self, client, mock_minio, tmp_path):
        with patch.object(client, "client") as m:
            m.fget_object.side_effect = RuntimeError("connection refused")

            with patch("rag.infrastructure.minio.storage.settings") as mock_cfg:
                mock_cfg.temp_dir = str(tmp_path / "tmp3")
                mock_cfg.minio_input_bucket = "bucket"

                with pytest.raises(RuntimeError, match="connection refused"):
                    await client.download_json("s3://bucket/fail.json")

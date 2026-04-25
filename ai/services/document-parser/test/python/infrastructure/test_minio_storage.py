"""Юнит-тесты для MinioStorage — все вызовы SDK замокированы."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from minio.error import S3Error

from docparser.infrastructure.minio import MinioStorage


@pytest.fixture
def mock_minio_client():
    """Патчим конструктор Minio, возвращаем MagicMock вместо реального клиента."""
    with patch("docparser.infrastructure.minio.Minio") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def storage(mock_minio_client) -> MinioStorage:
    return MinioStorage()


# ── download_file ─────────────────────────────────────────────────────────────

async def test_download_file_calls_fget_object(storage, mock_minio_client):
    """download_file должен вызывать fget_object с правильными аргументами."""
    mock_minio_client.fget_object = MagicMock(return_value=None)
    await storage.download_file("bucket", "file.htm", "/tmp/file.htm")
    mock_minio_client.fget_object.assert_called_once_with("bucket", "file.htm", "/tmp/file.htm")


async def test_download_file_is_awaitable(storage, mock_minio_client):
    """download_file должен быть корутиной."""
    mock_minio_client.fget_object = MagicMock(return_value=None)
    result = await storage.download_file("bucket", "obj", "/tmp/f")
    assert result is None


# ── upload_json ───────────────────────────────────────────────────────────────

async def test_upload_json_creates_bucket_if_not_exists(storage, mock_minio_client):
    """Если корзина не существует — должна быть создана."""
    mock_minio_client.bucket_exists = MagicMock(return_value=False)
    mock_minio_client.make_bucket = MagicMock()
    mock_minio_client.put_object = MagicMock()

    await storage.upload_json("new-bucket", "doc.json", {"key": "value"})

    mock_minio_client.make_bucket.assert_called_once_with("new-bucket")


async def test_upload_json_skips_bucket_creation_if_exists(storage, mock_minio_client):
    """Если корзина уже существует — make_bucket не должен вызываться."""
    mock_minio_client.bucket_exists = MagicMock(return_value=True)
    mock_minio_client.put_object = MagicMock()

    await storage.upload_json("existing-bucket", "doc.json", {"key": "value"})

    mock_minio_client.make_bucket.assert_not_called()


async def test_upload_json_calls_put_object_with_json_content_type(storage, mock_minio_client):
    """put_object должен вызываться с content_type='application/json'."""
    mock_minio_client.bucket_exists = MagicMock(return_value=True)
    mock_minio_client.put_object = MagicMock()

    await storage.upload_json("bucket", "doc.json", {"data": 123})

    call_kwargs = mock_minio_client.put_object.call_args
    assert call_kwargs.kwargs.get("content_type") == "application/json"


# ── object_exists ─────────────────────────────────────────────────────────────

async def test_object_exists_returns_true_when_stat_succeeds(storage, mock_minio_client):
    """stat_object не бросает исключение → объект существует → True."""
    mock_minio_client.stat_object = MagicMock(return_value=MagicMock())
    result = await storage.object_exists("bucket", "doc.json")
    assert result is True


async def test_object_exists_returns_false_on_no_such_key(storage, mock_minio_client):
    """S3Error с кодом NoSuchKey → объект не найден → False."""
    error = S3Error(
        code="NoSuchKey",
        message="Object not found",
        resource="bucket/doc.json",
        request_id="req-1",
        host_id="host-1",
        response=MagicMock(status=404),
    )
    mock_minio_client.stat_object = MagicMock(side_effect=error)
    result = await storage.object_exists("bucket", "doc.json")
    assert result is False


async def test_object_exists_reraises_other_s3_errors(storage, mock_minio_client):
    """S3Error с другим кодом должен быть пробошен наверх."""
    error = S3Error(
        code="AccessDenied",
        message="Access denied",
        resource="bucket/doc.json",
        request_id="req-1",
        host_id="host-1",
        response=MagicMock(status=403),
    )
    mock_minio_client.stat_object = MagicMock(side_effect=error)

    with pytest.raises(S3Error):
        await storage.object_exists("bucket", "doc.json")


async def test_download_file_retries_on_connection_error(storage, mock_minio_client):
    """ConnectionError должен триггерить retry (2 ошибки + успех на 3-й попытке)."""
    mock_minio_client.fget_object = MagicMock(
        side_effect=[ConnectionError("timeout"), ConnectionError("timeout"), None]
    )
    # Не должно вызвать исключение — tenacity поймает и повторит
    await storage.download_file("bucket", "file.htm", "/tmp/file.htm")
    assert mock_minio_client.fget_object.call_count == 3

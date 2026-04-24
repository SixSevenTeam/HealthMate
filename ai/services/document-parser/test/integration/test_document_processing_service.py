"""Интеграционные тесты для DocumentProcessingService.

Все внешние зависимости (MinIO, Kafka, Processor) замокированы.
Проверяется оркестрация pipeline и обработка ошибок.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from minio.error import S3Error

from docparser.application import DocumentProcessingService
from docparser.domain import IncomingEvent


# ── Фикстура сервиса ──────────────────────────────────────────────────────────

@pytest.fixture
def service(mock_storage, mock_processor, mock_tree_builder, mock_producer):
    return DocumentProcessingService(
        storage=mock_storage,
        processor=mock_processor,
        tree_builder=mock_tree_builder,
        producer=mock_producer,
    )


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_process_event_happy_path(service, sample_event, mock_storage, mock_producer, tmp_path):
    """Полный успешный pipeline: скачать → распарсить → загрузить → отправить события."""
    mock_storage.object_exists = AsyncMock(return_value=False)

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    # Должен отправить финальный статус MARKDOWN_READY
    status_calls = [call.args[1] for call in mock_producer.send_status.call_args_list]
    assert "MARKDOWN_READY" in status_calls

    # Должен отправить итоговое событие
    mock_producer.send_event.assert_called_once()


async def test_process_event_idempotent_already_processed(
    service, sample_event, mock_storage, mock_producer, tmp_path
):
    """Если документ уже обработан — pipeline не должен запускаться повторно."""
    mock_storage.object_exists = AsyncMock(return_value=True)

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    # download_file НЕ должен вызываться
    mock_storage.download_file.assert_not_called()

    # Статус MARKDOWN_READY должен быть отправлен (идемпотентный ответ)
    status_calls = [call.args[1] for call in mock_producer.send_status.call_args_list]
    assert "MARKDOWN_READY" in status_calls

    # send_event должен вызваться (Java ждёт подтверждения)
    mock_producer.send_event.assert_called_once()


async def test_process_event_sends_processing_status_before_download(
    service, sample_event, mock_storage, mock_producer, tmp_path
):
    """Статус PROCESSING должен отправляться до начала скачивания."""
    mock_storage.object_exists = AsyncMock(return_value=False)

    statuses_in_order = []

    async def capture_status(doc_id, status, message):
        statuses_in_order.append(status)

    mock_producer.send_status.side_effect = capture_status

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    assert statuses_in_order[0] == "PROCESSING"


# ── Обработка ошибок ──────────────────────────────────────────────────────────

async def test_process_event_file_not_found_sends_failed_status(
    service, sample_event, mock_storage, mock_producer, tmp_path
):
    """S3Error NoSuchKey → статус FAILED, pipeline останавливается."""
    mock_storage.object_exists = AsyncMock(return_value=False)
    error = S3Error(
        code="NoSuchKey",
        message="Not found",
        resource="bucket/file.htm",
        request_id="r1",
        host_id="h1",
        response=None,
    )
    mock_storage.download_file = AsyncMock(side_effect=error)

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    status_calls = [call.args[1] for call in mock_producer.send_status.call_args_list]
    assert "FAILED" in status_calls
    mock_storage.upload_json.assert_not_called()


async def test_process_event_processor_failure_sends_failed_status(
    service, sample_event, mock_storage, mock_processor, mock_producer, tmp_path
):
    """Ошибка в Processor → статус FAILED."""
    mock_storage.object_exists = AsyncMock(return_value=False)
    mock_processor.convert_to_markdown = lambda _: (_ for _ in ()).throw(
        RuntimeError("Ошибка конвертации")
    )

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    status_calls = [call.args[1] for call in mock_producer.send_status.call_args_list]
    assert "FAILED" in status_calls


async def test_process_event_cleanup_called_even_on_failure(
    service, sample_event, mock_storage, mock_producer, tmp_path
):
    """Временный файл должен удаляться даже при ошибке."""
    mock_storage.object_exists = AsyncMock(return_value=False)
    mock_storage.download_file = AsyncMock(side_effect=Exception("Непредвиденная ошибка"))

    with patch("docparser.application.settings") as mock_settings, \
         patch("docparser.application.os.remove") as mock_remove, \
         patch("docparser.application.os.path.exists", return_value=True):
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    # os.remove должен быть вызван (cleanup в finally)
    mock_remove.assert_called_once()


async def test_process_event_outgoing_event_published_on_success(
    service, sample_event, mock_storage, mock_producer, tmp_path
):
    """При успехе send_event должен вызываться с корректным document_id."""
    mock_storage.object_exists = AsyncMock(return_value=False)

    with patch("docparser.application.settings") as mock_settings:
        mock_settings.minio_output_bucket = "output-bucket"
        mock_settings.temp_dir = str(tmp_path)
        await service.process_event(sample_event)

    call_args = mock_producer.send_event.call_args
    sent_event = call_args.args[0]
    assert sent_event.document_id == sample_event.id


# ── Тесты _parse_minio_path ───────────────────────────────────────────────────

def test_parse_minio_path_with_minio_prefix():
    bucket, obj = DocumentProcessingService._parse_minio_path(
        "minio://my-bucket/path/to/file.htm", "fallback"
    )
    assert bucket == "my-bucket"
    assert obj == "path/to/file.htm"


def test_parse_minio_path_with_bucket_prefix():
    bucket, obj = DocumentProcessingService._parse_minio_path(
        "raw-documents/file.htm", "raw-documents"
    )
    assert bucket == "raw-documents"
    assert obj == "file.htm"


def test_parse_minio_path_bare_object_name():
    bucket, obj = DocumentProcessingService._parse_minio_path(
        "file.htm", "fallback-bucket"
    )
    assert bucket == "fallback-bucket"
    assert obj == "file.htm"

"""Tests for StatusProducer (Kafka)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.infrastructure.kafka.producer import StatusProducer


class TestStatusProducer:

    @pytest.fixture
    def producer(self):
        p = StatusProducer()
        return p

    async def test_start_creates_producer(self, producer):
        with patch("rag.infrastructure.kafka.producer.AIOKafkaProducer") as mock_cls:
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance

            await producer.start()

            mock_cls.assert_called_once()
            mock_instance.start.assert_called_once()
            assert producer._producer is mock_instance

    async def test_send_status_success(self, producer):
        mock_kafka = AsyncMock()
        producer._producer = mock_kafka

        await producer.send_status(
            document_id="doc-1",
            status="embedded",
            details={"chunks_created": 5},
        )

        mock_kafka.send_and_wait.assert_called_once()
        call_kwargs = mock_kafka.send_and_wait.call_args
        assert call_kwargs[1]["key"] == b"doc-1"

    async def test_send_status_not_started_raises(self, producer):
        with pytest.raises(RuntimeError, match="Producer not started"):
            await producer.send_status(
                document_id="doc-1",
                status="embedded",
            )

    async def test_send_status_with_error(self, producer):
        mock_kafka = AsyncMock()
        producer._producer = mock_kafka

        await producer.send_status(
            document_id="doc-fail",
            status="failed",
            error={"message": "boom"},
        )

        mock_kafka.send_and_wait.assert_called_once()

    async def test_stop(self, producer):
        mock_kafka = AsyncMock()
        producer._producer = mock_kafka

        await producer.stop()

        mock_kafka.stop.assert_called_once()

    async def test_stop_noop_when_not_started(self, producer):
        await producer.stop()

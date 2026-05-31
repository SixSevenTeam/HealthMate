"""Tests for Settings configuration."""

from __future__ import annotations

from rag.core.config import Settings, settings, get_settings


class TestSettings:

    def test_defaults(self):
        assert settings.service_name == "rag-system"
        assert settings.embedding_dimension == 1024
        assert settings.chunk_size == 512
        assert settings.chunk_overlap == 128
        assert settings.min_chunk_size == 100
        assert settings.max_clarifying_questions == 3
        assert settings.retrieval_top_k == 10
        assert settings.embedding_batch_size == 100

    def test_postgres_url(self):
        url = settings.postgres_url
        assert url.startswith("postgresql+asyncpg://")
        assert settings.postgres_host in url

    def test_get_settings_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_qdrant_defaults(self):
        assert settings.qdrant_timeout == 30
        assert settings.qdrant_collection_name == "medical_documents"

    def test_kafka_defaults(self):
        assert settings.kafka_input_topic == "json-outgoing"
        assert settings.kafka_status_topic == "document.status"
        assert settings.kafka_consumer_group == "python-group"

    def test_minio_defaults(self):
        assert settings.minio_input_bucket == "processed-json-doc"
        assert settings.minio_secure is False

    def test_dialogue_defaults(self):
        assert settings.anamnesis_timeout_seconds == 300

    def test_hybrid_search_weights(self):
        assert settings.hybrid_search_weight_semantic == 0.7
        assert settings.hybrid_search_weight_lexical == 0.3

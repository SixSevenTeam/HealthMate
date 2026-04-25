"""Shared fixtures for RAG system tests."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Patch settings before any rag module is imported
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("LOG_FORMAT", "console")


@pytest.fixture
def sample_json_tree():
    """Sample JSON tree from document-parser."""
    from test.resources import load_json
    return load_json("stub/common/json_tree.json")


@pytest.fixture
def sample_user_profile():
    """Sample user profile dict."""
    return {
        "age": 35,
        "gender": "male",
        "allergies": ["аспирин"],
        "chronic_conditions": [{"name": "гипертония"}],
        "current_medications": [
            {"name": "лизиноприл", "dosage": "10 мг", "frequency": "1 раз/день"}
        ],
    }


@pytest.fixture
def sample_query_request(sample_user_profile):
    """Sample QueryRequest for testing dialogue."""
    from rag.domain.events import QueryRequest, UserProfile, ChronicCondition, Medication

    return QueryRequest(
        user_id="user-123",
        session_id="session-456",
        query="У меня болит голова уже два дня",
        user_profile=UserProfile(
            age=sample_user_profile["age"],
            gender=sample_user_profile["gender"],
            allergies=sample_user_profile["allergies"],
            chronic_conditions=[
                ChronicCondition(**c)
                for c in sample_user_profile["chronic_conditions"]
            ],
            current_medications=[
                Medication(**m)
                for m in sample_user_profile["current_medications"]
            ],
        ),
    )

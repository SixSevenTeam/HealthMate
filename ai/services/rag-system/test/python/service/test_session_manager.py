"""Tests for Session serialization and SessionManager."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.dialogue.session import Session, SessionManager, _SESSION_PREFIX
from rag.dialogue.stages import ConsultationStage


class TestSession:

    def test_create_default(self):
        s = Session(session_id="s1", user_id="u1")
        assert s.stage == ConsultationStage.ANAMNESIS
        assert s.questions_asked == 0
        assert s.collected_symptoms == []
        assert s.clinical_summary == ""
        assert s.messages == []

    def test_to_json(self):
        s = Session(session_id="s1", user_id="u1")
        raw = s.to_json()
        data = json.loads(raw)
        assert data["session_id"] == "s1"
        assert data["stage"] == "anamnesis_collection"
        assert isinstance(data["created_at"], str)

    def test_from_json_roundtrip(self):
        original = Session(
            session_id="s1",
            user_id="u1",
            stage=ConsultationStage.SYNTHESIS,
            questions_asked=3,
            collected_symptoms=["головная боль"],
            clinical_summary="test summary",
            messages=[{"role": "user", "content": "hello"}],
        )
        raw = original.to_json()
        restored = Session.from_json(raw)
        assert restored.session_id == "s1"
        assert restored.stage == ConsultationStage.SYNTHESIS
        assert restored.questions_asked == 3
        assert restored.collected_symptoms == ["головная боль"]
        assert restored.clinical_summary == "test summary"
        assert len(restored.messages) == 1

    def test_from_json_all_stages(self):
        for stage in ConsultationStage:
            s = Session(session_id="x", user_id="u", stage=stage)
            restored = Session.from_json(s.to_json())
            assert restored.stage == stage

    def test_to_json_preserves_unicode(self):
        s = Session(session_id="s1", user_id="u1", clinical_summary="Боль в суставах")
        raw = s.to_json()
        assert "Боль в суставах" in raw


class TestSessionManager:

    @pytest.fixture
    def mock_redis(self):
        redis_mock = AsyncMock()
        return redis_mock

    @pytest.fixture
    def manager(self, mock_redis):
        with patch("rag.dialogue.session.aioredis") as aioredis_mock:
            aioredis_mock.from_url.return_value = mock_redis
            mgr = SessionManager()
            mgr._redis = mock_redis
            mgr._ttl = 300
            return mgr

    async def test_get_or_create_new_session(self, manager, mock_redis):
        mock_redis.get.return_value = None
        session = await manager.get_or_create("s1", "u1")
        assert session.session_id == "s1"
        assert session.user_id == "u1"
        assert session.stage == ConsultationStage.ANAMNESIS
        mock_redis.setex.assert_called_once()

    async def test_get_or_create_existing_session(self, manager, mock_redis):
        existing = Session(
            session_id="s1",
            user_id="u1",
            stage=ConsultationStage.SYNTHESIS,
            questions_asked=2,
        )
        mock_redis.get.return_value = existing.to_json()
        session = await manager.get_or_create("s1", "u1")
        assert session.stage == ConsultationStage.SYNTHESIS
        assert session.questions_asked == 2

    async def test_update_sets_ttl(self, manager, mock_redis):
        session = Session(session_id="s1", user_id="u1")
        await manager.update(session)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == f"{_SESSION_PREFIX}s1"
        assert args[0][1] == 300

    async def test_delete(self, manager, mock_redis):
        await manager.delete("s1")
        mock_redis.delete.assert_called_once_with(f"{_SESSION_PREFIX}s1")

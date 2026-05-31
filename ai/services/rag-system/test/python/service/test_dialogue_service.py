"""Tests for DialogueService (3-stage logic)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.dialogue.service import DialogueService
from rag.dialogue.session import Session
from rag.dialogue.stages import ConsultationStage
from rag.domain.events import QueryRequest, UserProfile


def _make_request(**overrides) -> QueryRequest:
    defaults = {
        "user_id": "u1",
        "session_id": "s1",
        "query": "У меня болит голова",
        "user_profile": UserProfile(age=30, gender="male", allergies=["аспирин"]),
    }
    defaults.update(overrides)
    return QueryRequest(**defaults)


def _make_session(**overrides) -> Session:
    defaults = {
        "session_id": "s1",
        "user_id": "u1",
    }
    defaults.update(overrides)
    return Session(**defaults)


class TestDetermineStage:

    def setup_method(self):
        with patch("rag.dialogue.session.aioredis"):
            self.mock_sessions = AsyncMock()
            self.service = DialogueService(session_manager=self.mock_sessions)

    async def test_fresh_session_returns_anamnesis(self):
        session = _make_session()
        req = _make_request()
        stage = await self.service._determine_stage(session, req)
        assert stage == ConsultationStage.ANAMNESIS

    async def test_max_questions_triggers_synthesis(self):
        session = _make_session(questions_asked=3)
        req = _make_request()
        with patch("rag.dialogue.service.settings") as mock_settings:
            mock_settings.max_clarifying_questions = 3
            stage = await self.service._determine_stage(session, req)
            assert stage == ConsultationStage.SYNTHESIS

    async def test_clinical_summary_triggers_recommendation(self):
        session = _make_session(clinical_summary="test summary")
        req = _make_request()
        stage = await self.service._determine_stage(session, req)
        assert stage == ConsultationStage.RECOMMENDATION

    async def test_recommendation_stage_stays(self):
        session = _make_session(stage=ConsultationStage.RECOMMENDATION)
        req = _make_request()
        stage = await self.service._determine_stage(session, req)
        assert stage == ConsultationStage.RECOMMENDATION

    async def test_synthesis_stage_stays(self):
        session = _make_session(stage=ConsultationStage.SYNTHESIS)
        req = _make_request()
        stage = await self.service._determine_stage(session, req)
        assert stage == ConsultationStage.SYNTHESIS


class TestCollectAnamnesis:

    @pytest.fixture
    def service(self):
        mock_sessions = AsyncMock()
        return DialogueService(session_manager=mock_sessions)

    @patch("rag.dialogue.service.get_llm_client")
    async def test_anamnesis_returns_question(self, mock_get_llm, service):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "Как давно у вас болит голова?"
        mock_get_llm.return_value = mock_llm

        session = _make_session()
        req = _make_request()
        response = await service._collect_anamnesis(req, session)

        assert response.stage == "anamnesis_collection"
        assert response.response_type == "clarifying_question"
        assert "Как давно" in response.content["message"]
        assert response.next_action == "await_user_response"
        assert session.questions_asked == 1

    @patch("rag.dialogue.service.get_llm_client")
    async def test_anamnesis_updates_session(self, mock_get_llm, service):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "Вопрос?"
        mock_get_llm.return_value = mock_llm

        session = _make_session()
        req = _make_request()
        await service._collect_anamnesis(req, session)

        service._sessions.update.assert_called_once()


class TestSynthesizeContext:

    @pytest.fixture
    def service(self):
        mock_sessions = AsyncMock()
        return DialogueService(session_manager=mock_sessions)

    @patch("rag.dialogue.service.get_llm_client")
    async def test_synthesis_returns_summary(self, mock_get_llm, service):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "Клиническая картина: головная боль 2 дня"
        mock_get_llm.return_value = mock_llm

        session = _make_session(questions_asked=3)
        req = _make_request()
        response = await service._synthesize_context(req, session)

        assert response.stage == "context_synthesis"
        assert session.clinical_summary == "Клиническая картина: головная боль 2 дня"
        assert session.stage == ConsultationStage.RECOMMENDATION


class TestGenerateRecommendation:

    @pytest.fixture
    def service(self):
        mock_sessions = AsyncMock()
        return DialogueService(session_manager=mock_sessions)

    @patch("rag.dialogue.service.get_llm_client")
    @patch("rag.retrieval.retriever.get_retriever")
    async def test_recommendation_contains_disclaimer(
        self, mock_get_retriever, mock_get_llm, service
    ):
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = []
        mock_get_retriever.return_value = mock_retriever

        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "Рекомендую парацетамол"
        mock_get_llm.return_value = mock_llm

        session = _make_session(
            clinical_summary="головная боль",
            stage=ConsultationStage.RECOMMENDATION,
        )
        req = _make_request()
        response = await service._generate_recommendation(req, session)

        assert response.stage == "recommendation"
        assert "Важно" in response.content["message"]
        assert response.next_action == "session_complete"
        service._sessions.delete.assert_called_once()

    @patch("rag.dialogue.service.get_llm_client")
    @patch("rag.retrieval.retriever.get_retriever")
    async def test_recommendation_with_chunks(
        self, mock_get_retriever, mock_get_llm, service
    ):
        from rag.retrieval.retriever import RetrievedChunk

        chunk = RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            text="Парацетамол: 500 мг",
            score=0.9,
            metadata={"section_path": ["Дозировка"]},
        )
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [chunk]
        mock_get_retriever.return_value = mock_retriever

        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "Рекомендация"
        mock_get_llm.return_value = mock_llm

        session = _make_session(clinical_summary="headache")
        req = _make_request()
        response = await service._generate_recommendation(req, session)

        assert len(response.context_used.retrieved_documents) == 1
        assert response.context_used.retrieved_documents[0].document_id == "d1"


class TestFormatProfile:

    def test_full_profile(self):
        req = _make_request(
            user_profile=UserProfile(
                age=30,
                gender="male",
                allergies=["аспирин"],
            )
        )
        result = DialogueService._format_profile(req)
        assert "Возраст: 30" in result
        assert "Пол: male" in result
        assert "аспирин" in result

    def test_empty_profile(self):
        req = _make_request(user_profile=UserProfile())
        result = DialogueService._format_profile(req)
        assert result == "Профиль не указан"

"""Tests for /ai/chat endpoint (контракт Васе)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from rag.api.endpoints.chat import (
    AiChatRequest,
    AiChatResponse,
    AiChatUserContext,
    AiChatAllergy,
    AiChatDiagnosis,
    AiChatActiveMedication,
    AiChatMessage,
    _to_query_request,
)
from test.resources import load_json


class TestToQueryRequest:

    def test_basic_mapping(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(
                userId="u1",
                allergies=[AiChatAllergy(allergen="аспирин", reaction="сыпь")],
            ),
            userMessage="test message",
        )
        qr = _to_query_request(req)
        assert qr.user_id == "u1"
        assert qr.session_id == "s1"
        assert qr.query == "test message"
        assert qr.user_profile.allergies == ["аспирин"]

    def test_with_medications(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(
                userId="u1",
                activeMedications=[
                    AiChatActiveMedication(
                        tradeName="лизиноприл",
                        doseAmount=10,
                        doseUnit="мг",
                        instructions="1р/д",
                    )
                ],
            ),
            userMessage="msg",
        )
        qr = _to_query_request(req)
        assert len(qr.user_profile.current_medications) == 1
        assert qr.user_profile.current_medications[0].name == "лизиноприл"

    def test_with_diagnoses(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(
                userId="u1",
                diagnoses=[
                    AiChatDiagnosis(name="гипертония"),
                    AiChatDiagnosis(name="диабет"),
                ],
            ),
            userMessage="msg",
        )
        qr = _to_query_request(req)
        assert len(qr.user_profile.chronic_conditions) == 2

    def test_with_history(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(userId="u1"),
            userMessage="msg",
            conversationHistory=[
                AiChatMessage(role="user", content="hi"),
            ],
        )
        qr = _to_query_request(req)
        assert len(qr.conversation_history) == 1

    def test_anamnesis_state_passthrough(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(userId="u1"),
            userMessage="msg",
            anamnesisState={"stage": "collecting"},
        )
        assert req.anamnesisState == {"stage": "collecting"}

    def test_context_degraded_fields(self):
        req = AiChatRequest(
            conversationId="s1",
            userContext=AiChatUserContext(
                userId="u1",
                contextDegraded=True,
                contextWarnings=["partial data"],
            ),
            userMessage="msg",
        )
        assert req.userContext.contextDegraded is True
        assert req.userContext.contextWarnings == ["partial data"]


class TestAiChatEndpoint:

    @staticmethod
    def _build_query_response(stub_path: str):
        from rag.domain.events import ContextUsed, QueryResponse, ResponseMetadata
        stub = load_json(stub_path)
        return QueryResponse(
            request_id=stub["request_id"],
            session_id=stub["session_id"],
            stage=stub["stage"],
            response_type=stub["response_type"],
            content=stub["content"],
            next_action=stub["next_action"],
            context_used=ContextUsed(),
            metadata=ResponseMetadata(
                processing_time_ms=stub.get("processing_time_ms", 0),
                llm_model=stub.get("llm_model", "test"),
                questions_asked=stub.get("questions_asked", 0),
            ),
        )

    async def test_chat_success(self):
        from rag.api.deps import get_dialogue_service_dep

        mock_service = AsyncMock()
        mock_service.process_query.return_value = self._build_query_response(
            "stub/chat/anamnesis_query_response.json"
        )

        from main import app

        request_body = load_json("request/chat/chat_minimal.json")
        app.dependency_overrides[get_dialogue_service_dep] = lambda: mock_service
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/ai/chat", json=request_body)

            expected = load_json("expected/chat/anamnesis_response.json")
            assert resp.status_code == 200
            data = resp.json()
            assert data["messageType"] == expected["messageType"]
            assert data["anamnesisState"] == expected["anamnesisState"]
            assert isinstance(data["recommendedDrugs"], list)
        finally:
            app.dependency_overrides.clear()

    async def test_chat_response_contract_fields(self):
        """Проверяем, что все поля контракта Васе присутствуют в ответе."""
        from rag.api.deps import get_dialogue_service_dep

        mock_service = AsyncMock()
        mock_service.process_query.return_value = self._build_query_response(
            "stub/chat/recommendation_query_response.json"
        )

        from main import app

        request_body = load_json("request/chat/chat_minimal.json")
        app.dependency_overrides[get_dialogue_service_dep] = lambda: mock_service
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/ai/chat", json=request_body)
            assert resp.status_code == 200
            data = resp.json()
            expected = load_json("expected/chat/recommendation_response.json")
            required_keys = set(expected["required_fields"])
            assert required_keys.issubset(data.keys())
            assert data["messageType"] == expected["messageType"]
            assert data["anamnesisState"] == expected["anamnesisState"]
        finally:
            app.dependency_overrides.clear()

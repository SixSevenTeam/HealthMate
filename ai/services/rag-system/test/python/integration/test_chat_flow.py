"""Integration test: full 3-stage medical dialogue via HTTP.

Scenario:
  1. User sends symptom -> gets clarifying question (ANAMNESIS x3).
  2. System transitions to SYNTHESIS -> builds clinical summary.
  3. System transitions to RECOMMENDATION -> returns final answer + disclaimer.

Fakes: fakeredis (in-process), mock LLM, mock retriever.
Real:  DialogueService, SessionManager, SafetyChecker, FastAPI app.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from rag.dialogue.service import DialogueService
from rag.dialogue.session import SessionManager
from rag.retrieval.retriever import RetrievedChunk
from test.resources import load_json


def _chat_body(conv_id: str, msg: str) -> dict:
    ctx = load_json("request/common/user_context.json")
    return {
        "conversationId": conv_id,
        "userMessage": msg,
        "userContext": ctx,
        "conversationHistory": [],
    }


def _load_llm_answers() -> list[str]:
    data = load_json("stub/common/llm_responses.json")
    return [
        data["anamnesis_question_1"],
        data["anamnesis_question_2"],
        data["anamnesis_question_3"],
        data["synthesis_summary"],
        data["recommendation"],
    ]


def _load_chunks() -> list[RetrievedChunk]:
    raw = load_json("stub/common/retrieved_chunks.json")
    return [
        RetrievedChunk(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            text=c["text"],
            score=c["score"],
            metadata=c["metadata"],
        )
        for c in raw
    ]


class TestFullChatFlow:

    @pytest.fixture
    async def wired_app(self):
        """Wire real services with fakeredis and mock LLM/retriever."""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        sm = SessionManager.__new__(SessionManager)
        sm._redis = fake_redis
        sm._ttl = 300

        svc = DialogueService(session_manager=sm)

        from rag.api.deps import get_dialogue_service_dep
        from main import app

        app.dependency_overrides[get_dialogue_service_dep] = lambda: svc
        yield app
        app.dependency_overrides.clear()
        await fake_redis.aclose()

    async def test_three_stage_dialogue(self, wired_app):
        llm_iter = iter(_load_llm_answers())

        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = lambda *a, **kw: next(llm_iter)

        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = _load_chunks()

        with (
            patch("rag.dialogue.service.get_llm_client", return_value=mock_llm),
            patch("rag.retrieval.retriever.get_retriever", return_value=mock_retriever),
        ):
            transport = ASGITransport(app=wired_app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:

                # --- Step 1: ANAMNESIS (question 1) ---
                r1 = await c.post("/ai/chat", json=_chat_body("conv-1", "I have a headache"))
                assert r1.status_code == 200
                d1 = r1.json()
                assert d1["messageType"] == "question"
                assert d1["anamnesisState"] == {"stage": "collecting"}

                # --- Step 2: ANAMNESIS (question 2) ---
                r2 = await c.post("/ai/chat", json=_chat_body("conv-1", "2 days"))
                assert r2.status_code == 200
                d2 = r2.json()
                assert d2["messageType"] == "question"

                # --- Step 3: ANAMNESIS (question 3) ---
                r3 = await c.post("/ai/chat", json=_chat_body("conv-1", "no"))
                assert r3.status_code == 200
                d3 = r3.json()
                assert d3["messageType"] == "question"

                # --- Step 4: SYNTHESIS (auto-transition, questions_asked=3) ---
                r4 = await c.post("/ai/chat", json=_chat_body("conv-1", "nothing else"))
                assert r4.status_code == 200
                d4 = r4.json()
                assert d4["messageType"] == "info"

                # --- Step 5: RECOMMENDATION ---
                r5 = await c.post("/ai/chat", json=_chat_body("conv-1", "ok"))
                assert r5.status_code == 200
                d5 = r5.json()
                assert d5["anamnesisState"] == {"stage": "completed"}
                assert d5["disclaimer"] is not None

        # Verify LLM was called 5 times (3 anamnesis + 1 synthesis + 1 recommendation)
        assert mock_llm.chat.call_count == 5

    async def test_medication_validate_during_chat(self, wired_app):
        """Validate endpoint works alongside chat (both registered)."""
        request_body = load_json("request/medications/validate_aspirin.json")
        transport = ASGITransport(app=wired_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/ai/medications/validate", json=request_body)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "danger"
            assert len(data["blockers"]) > 0

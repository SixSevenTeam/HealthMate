"""Tests for /api/v1/query endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from rag.domain.events import (
    ContextUsed,
    QueryRequest,
    QueryResponse,
    ResponseMetadata,
    UserProfile,
)


class TestQueryEndpoint:

    async def test_query_success(self):
        from rag.api.deps import get_dialogue_service_dep
        from main import app

        mock_service = AsyncMock()
        mock_service.process_query.return_value = QueryResponse(
            request_id="r1",
            session_id="s1",
            stage="anamnesis_collection",
            response_type="clarifying_question",
            content={"message": "question", "disclaimer": "d"},
            next_action="await_user_response",
            context_used=ContextUsed(),
            metadata=ResponseMetadata(
                processing_time_ms=50,
                llm_model="test",
                questions_asked=1,
            ),
        )

        app.dependency_overrides[get_dialogue_service_dep] = lambda: mock_service
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/query",
                    json={
                        "user_id": "u1",
                        "session_id": "s1",
                        "query": "test query",
                        "user_profile": {},
                    },
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == "s1"
            assert data["stage"] == "anamnesis_collection"
        finally:
            app.dependency_overrides.clear()

    async def test_query_error_returns_500(self):
        from rag.api.deps import get_dialogue_service_dep
        from main import app

        mock_service = AsyncMock()
        mock_service.process_query.side_effect = RuntimeError("boom")

        app.dependency_overrides[get_dialogue_service_dep] = lambda: mock_service
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/query",
                    json={
                        "user_id": "u1",
                        "session_id": "s1",
                        "query": "fail",
                        "user_profile": {},
                    },
                )
            assert resp.status_code == 500
        finally:
            app.dependency_overrides.clear()

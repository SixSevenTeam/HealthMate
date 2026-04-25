"""Tests for domain event models (Pydantic)."""

from __future__ import annotations

import pytest

from rag.domain.events import (
    ChronicCondition,
    ConversationMessage,
    ContextUsed,
    DocumentParsedEvent,
    DocumentStatusEvent,
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentStatusResponse,
    Medication,
    QueryMetadata,
    QueryRequest,
    QueryResponse,
    ResponseMetadata,
    RetrievedDocument,
    UserProfile,
)


class TestUserProfile:

    def test_defaults(self):
        p = UserProfile()
        assert p.age is None
        assert p.allergies == []
        assert p.chronic_conditions == []
        assert p.current_medications == []

    def test_full_profile(self):
        p = UserProfile(
            age=30,
            gender="male",
            allergies=["аспирин"],
            chronic_conditions=[ChronicCondition(name="диабет", severity="moderate")],
            current_medications=[
                Medication(name="метформин", dosage="500 мг", frequency="2р/д")
            ],
        )
        assert p.age == 30
        assert len(p.chronic_conditions) == 1
        assert p.chronic_conditions[0].severity == "moderate"


class TestQueryRequest:

    def test_minimal(self):
        req = QueryRequest(
            user_id="u1",
            session_id="s1",
            query="test",
            user_profile=UserProfile(),
        )
        assert req.conversation_history == []
        assert req.metadata.language == "ru"

    def test_with_history(self):
        req = QueryRequest(
            user_id="u1",
            session_id="s1",
            query="test",
            user_profile=UserProfile(),
            conversation_history=[
                ConversationMessage(role="user", content="hello", timestamp="2024-01-01"),
            ],
        )
        assert len(req.conversation_history) == 1


class TestQueryResponse:

    def test_create_response(self):
        resp = QueryResponse(
            request_id="r1",
            session_id="s1",
            stage="anamnesis_collection",
            response_type="clarifying_question",
            content={"message": "test"},
            next_action="await_user_response",
        )
        assert resp.stage == "anamnesis_collection"
        assert resp.context_used.retrieved_documents == []

    def test_with_context(self):
        resp = QueryResponse(
            request_id="r1",
            session_id="s1",
            stage="recommendation",
            response_type="medical_recommendation",
            content={"message": "take pills"},
            next_action="session_complete",
            context_used=ContextUsed(
                retrieved_documents=[
                    RetrievedDocument(document_id="d1", relevance_score=0.95, snippet="txt")
                ],
                user_constraints_applied=["allergy:аспирин"],
                safety_checks_performed=["no_issues_found"],
            ),
        )
        assert len(resp.context_used.retrieved_documents) == 1
        assert resp.context_used.retrieved_documents[0].relevance_score == 0.95


class TestDocumentParsedEvent:

    def test_parse(self):
        event = DocumentParsedEvent(
            document_id="doc-1",
            s3_url="s3://bucket/doc-1.json",
            metadata={
                "title": "Test",
                "category": "medication",
                "language": "ru",
                "source_filename": "test.htm",
                "page_count": 1,
                "parsed_at": "2024-01-01T00:00:00Z",
                "parser_version": "0.1.0",
            },
            structure={
                "type": "hierarchical",
                "format": "tree_json",
                "total_nodes": 5,
                "max_depth": 2,
            },
        )
        assert event.document_id == "doc-1"
        assert event.metadata.category == "medication"


class TestDocumentStatusEvent:

    def test_to_dict(self):
        event = DocumentStatusEvent(
            document_id="d1",
            status="embedded",
            details={"chunks_created": 10},
        )
        d = event.to_dict()
        assert d["document_id"] == "d1"
        assert d["status"] == "embedded"
        assert "error" not in d

    def test_to_dict_with_error(self):
        event = DocumentStatusEvent(
            document_id="d1",
            status="failed",
            error={"message": "fail"},
        )
        d = event.to_dict()
        assert d["error"]["message"] == "fail"


class TestDocumentUpload:

    def test_upload_request(self):
        req = DocumentUploadRequest(document_id="d1", s3_url="s3://b/f.json")
        assert req.metadata == {}

    def test_upload_response_defaults(self):
        resp = DocumentUploadResponse(document_id="d1")
        assert resp.status == "queued"

    def test_status_response(self):
        resp = DocumentStatusResponse(document_id="d1", status="embedded")
        assert resp.progress is None

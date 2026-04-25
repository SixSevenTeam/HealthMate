"""Tests for POST /ai/medications/validate endpoint (контракт Васе)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from rag.api.endpoints.medications import (
    CandidateMedication,
    MedicationSafetyRequest,
    MedicationSafetyResponse,
    MedValidationAllergy,
    MedValidationActiveMedication,
    MedValidationDiagnosis,
    MedValidationUserContext,
)
from test.resources import load_json


class TestMedicationModels:

    def test_request_model(self):
        req = MedicationSafetyRequest(
            userId="u1",
            userContext=MedValidationUserContext(userId="u1"),
            candidateMedication=CandidateMedication(customName="Ibuprofen"),
        )
        assert req.userId == "u1"
        assert req.candidateMedication.customName == "Ibuprofen"

    def test_user_context_full(self):
        ctx = MedValidationUserContext(
            userId="u1",
            birthDate="1990-01-15",
            heightCm=178,
            weightKg=76.5,
            bloodType="A+",
            diagnoses=[MedValidationDiagnosis(name="Hypertension")],
            allergies=[MedValidationAllergy(allergen="Penicillin", reaction="Rash")],
            contextDegraded=False,
            contextWarnings=[],
            activeMedications=[
                MedValidationActiveMedication(
                    tradeName="Ibuprofen",
                    internationalName="Ibuprofen",
                    doseAmount=200,
                    doseUnit="mg",
                    instructions="after meal",
                )
            ],
        )
        assert ctx.heightCm == 178
        assert len(ctx.activeMedications) == 1

    def test_response_model(self):
        resp = MedicationSafetyResponse(
            status="ok",
            warnings=[],
            blockers=[],
            metadata={},
        )
        assert resp.status == "ok"


class TestMedicationsEndpoint:

    @staticmethod
    async def _post_validate(request_resource: str) -> dict:
        from main import app
        body = load_json(request_resource)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/ai/medications/validate", json=body)
        assert resp.status_code == 200
        return resp.json()

    async def test_validate_ok(self):
        data = await self._post_validate("request/medications/validate_safe.json")
        expected = load_json("expected/medications/ok_response.json")
        assert data["status"] == expected["status"]
        assert isinstance(data["warnings"], list)
        assert isinstance(data["blockers"], list)
        assert isinstance(data["metadata"], dict)

    async def test_validate_allergy_blocker(self):
        data = await self._post_validate("request/medications/validate_aspirin.json")
        expected = load_json("expected/medications/danger_response.json")
        assert data["status"] == expected["status"]
        assert len(data["blockers"]) > 0

    async def test_validate_drug_interaction(self):
        data = await self._post_validate("request/medications/validate_drug_interaction.json")
        assert data["status"] == "danger"
        assert len(data["blockers"]) > 0

    async def test_validate_chronic_condition(self):
        data = await self._post_validate("request/medications/validate_chronic_condition.json")
        assert data["status"] == "danger"

    async def test_validate_warning_status(self):
        data = await self._post_validate("request/medications/validate_safe.json")
        assert data["status"] in ("ok", "warning")

    async def test_response_contract_fields(self):
        """Все поля контракта Васе присутствуют."""
        data = await self._post_validate("request/medications/validate_minimal.json")
        expected = load_json("expected/medications/ok_response.json")
        required_keys = set(expected["required_fields"])
        assert required_keys.issubset(data.keys())

"""Эндпоинт POST /ai/medications/validate — проверка безопасности лекарства.

Java вызывает этот endpoint из AIGatewayService.validateMedication(...)
перед добавлением нового препарата в лист пользователя.
Формат запроса/ответа соответствует контракту из гайда endpoint Васе.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from rag.medical.safety_checker import SafetyChecker, get_safety_checker
from rag.domain.events import Medication

log = structlog.get_logger()

router = APIRouter()


# ── Модели запроса (контракт Васе) ──────────────────────────────────────────

class MedValidationDiagnosis(BaseModel):
    name: str
    diagnosedAt: str | None = Field(default=None, alias="diagnosedAt")


class MedValidationAllergy(BaseModel):
    allergen: str
    reaction: str | None = None


class MedValidationActiveMedication(BaseModel):
    tradeName: str | None = Field(default=None, alias="tradeName")
    internationalName: str | None = Field(default=None, alias="internationalName")
    doseAmount: float | None = Field(default=None, alias="doseAmount")
    doseUnit: str | None = Field(default=None, alias="doseUnit")
    instructions: str | None = None


class MedValidationUserContext(BaseModel):
    userId: str = Field(alias="userId")
    birthDate: str | None = Field(default=None, alias="birthDate")
    heightCm: float | None = Field(default=None, alias="heightCm")
    weightKg: float | None = Field(default=None, alias="weightKg")
    bloodType: str | None = Field(default=None, alias="bloodType")
    diagnoses: list[MedValidationDiagnosis] = Field(default_factory=list)
    allergies: list[MedValidationAllergy] = Field(default_factory=list)
    contextDegraded: bool = Field(default=False, alias="contextDegraded")
    contextWarnings: list[str] = Field(default_factory=list, alias="contextWarnings")
    activeMedications: list[MedValidationActiveMedication] = Field(
        default_factory=list, alias="activeMedications"
    )
    model_config = {"populate_by_name": True}


class CandidateMedication(BaseModel):
    drugId: str | None = Field(default=None, alias="drugId")
    customName: str | None = Field(default=None, alias="customName")
    doseAmount: float | None = Field(default=None, alias="doseAmount")
    doseUnit: str | None = Field(default=None, alias="doseUnit")
    instructions: str | None = None
    startDate: str | None = Field(default=None, alias="startDate")
    endDate: str | None = Field(default=None, alias="endDate")
    model_config = {"populate_by_name": True}


class MedicationSafetyRequest(BaseModel):
    """Запрос на валидацию лекарства (контракт Васе)."""
    userId: str = Field(alias="userId")
    userContext: MedValidationUserContext = Field(alias="userContext")
    candidateMedication: CandidateMedication = Field(alias="candidateMedication")
    model_config = {"populate_by_name": True}


# ── Модели ответа (контракт Васе) ───────────────────────────────────────────

class MedicationSafetyResponse(BaseModel):
    """Ответ валидации лекарства (контракт Васе)."""
    status: str
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.post(
    "/ai/medications/validate",
    response_model=MedicationSafetyResponse,
    summary="Проверка безопасности лекарства (Java → Python)",
    description=(
        "Проверяет, безопасно ли добавление нового препарата с учётом "
        "аллергий, текущих лекарств и хронических заболеваний пользователя."
    ),
    status_code=status.HTTP_200_OK,
)
async def validate_medication(
    request: MedicationSafetyRequest,
) -> MedicationSafetyResponse:
    """Валидирует безопасность кандидата-лекарства для пользователя."""
    log.info(
        "medication_validate_called",
        user_id=request.userId,
        candidate=request.candidateMedication.customName
        or request.candidateMedication.drugId,
    )

    try:
        checker = get_safety_checker()
        ctx = request.userContext
        candidate = request.candidateMedication
        med_name = candidate.customName or candidate.drugId or "unknown"

        all_warnings: list[str] = []
        all_blockers: list[str] = []

        # 1. Проверка аллергий
        allergy_names = [a.allergen for a in ctx.allergies]
        allergy_results = checker.check_allergies([med_name], allergy_names)
        for w in allergy_results:
            if w.severity == "high":
                all_blockers.append(w.reason)
            else:
                all_warnings.append(w.reason)

        # 2. Проверка взаимодействий с текущими лекарствами
        current_meds = [
            Medication(
                name=m.tradeName or m.internationalName or "",
                dosage=f"{m.doseAmount} {m.doseUnit}" if m.doseAmount else "",
                frequency=m.instructions or "",
            )
            for m in ctx.activeMedications
        ]
        interaction_results = checker.check_drug_interactions([med_name], current_meds)
        for w in interaction_results:
            if w.severity == "high":
                all_blockers.append(w.reason)
            else:
                all_warnings.append(w.reason)

        # 3. Проверка хронических заболеваний
        condition_names = [d.name.lower() for d in ctx.diagnoses]
        condition_results = checker.check_chronic_conditions([med_name], condition_names)
        for w in condition_results:
            if w.severity == "high":
                all_blockers.append(w.reason)
            else:
                all_warnings.append(w.reason)

        # Определяем итоговый статус
        if all_blockers:
            result_status = "danger"
        elif all_warnings:
            result_status = "warning"
        else:
            result_status = "ok"

        return MedicationSafetyResponse(
            status=result_status,
            warnings=all_warnings,
            blockers=all_blockers,
            metadata={
                "checks_performed": [
                    "allergy_check",
                    "drug_interaction_check",
                    "chronic_condition_check",
                ],
                "candidate_medication": med_name,
            },
        )

    except Exception as exc:
        log.error(
            "medication_validate_error",
            user_id=request.userId,
            error=str(exc),
        )
        return MedicationSafetyResponse(
            status="unavailable",
            warnings=[],
            blockers=[],
            metadata={"error": str(exc)},
        )

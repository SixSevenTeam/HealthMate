"""Эндпоинт POST /ai/medications/validate — проверка безопасности лекарства.

Java вызывает этот endpoint из AIGatewayService.validateMedication(...)
перед добавлением нового препарата в лист пользователя.
Формат запроса/ответа соответствует контракту из гайда endpoint Васе.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from rag.core.llm_client import get_llm_client
from rag.core.config import settings
from rag.medical.drugs_client import get_drug_by_id
import json

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


class _EmptyUserContext(MedValidationUserContext):
    userId: str = "unknown"


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
    userId: str = Field(default="unknown", alias="userId")
    userContext: MedValidationUserContext = Field(
        default_factory=_EmptyUserContext, alias="userContext"
    )
    candidateMedication: CandidateMedication = Field(
        default_factory=CandidateMedication, alias="candidateMedication"
    )
    model_config = {"populate_by_name": True}

    @staticmethod
    def _coerce_date_value(value: Any) -> Any:
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            year, month, day = value[0], value[1], value[2]
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except Exception:
                return value
        return value

    @classmethod
    def _normalize_nested_dates(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        candidate = normalized.get("candidateMedication")
        if isinstance(candidate, dict):
            candidate = dict(candidate)
            candidate["startDate"] = cls._coerce_date_value(candidate.get("startDate"))
            candidate["endDate"] = cls._coerce_date_value(candidate.get("endDate"))
            normalized["candidateMedication"] = candidate

        user_context = normalized.get("userContext")
        if isinstance(user_context, dict):
            user_context = dict(user_context)
            user_context["birthDate"] = cls._coerce_date_value(user_context.get("birthDate"))
            normalized["userContext"] = user_context

        return normalized

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_flat_payload(cls, data: Any) -> Any:
        """Поддерживает старый плоский payload из фронта без 422.

        Если фронт шлёт поля `customName`, `drugId`, `doseAmount` и т.д.
        на верхнем уровне, собираем из них структурированный контракт.
        """
        if not isinstance(data, dict):
            return data

        data = cls._normalize_nested_dates(data)

        if "candidateMedication" not in data:
            candidate_source = {
                "drugId": data.get("drugId"),
                "customName": data.get("customName"),
                "doseAmount": data.get("doseAmount"),
                "doseUnit": data.get("doseUnit"),
                "instructions": data.get("instructions"),
                "startDate": data.get("startDate"),
                "endDate": data.get("endDate"),
            }
            data = {**data, "candidateMedication": candidate_source}

        if "userContext" not in data:
            data = {
                **data,
                "userContext": {
                    "userId": data.get("userId") or "unknown",
                    "diagnoses": [],
                    "allergies": [],
                    "contextDegraded": True,
                    "contextWarnings": ["legacy_flat_payload"],
                    "activeMedications": [],
                },
            }

        if not data.get("userId"):
            data["userId"] = data.get("userContext", {}).get("userId") or "unknown"

        return data


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
    request: dict[str, Any],
) -> MedicationSafetyResponse:
    """Валидирует безопасность кандидата-лекарства для пользователя."""
    try:
        request = MedicationSafetyRequest.model_validate(request)
    except Exception as exc:
        log.warning("medication_validate_request_parse_failed", error=str(exc), request_type=str(type(request)))
        request = MedicationSafetyRequest()

    log.info(
        "medication_validate_called",
        user_id=request.userId,
        candidate=request.candidateMedication.customName
        or request.candidateMedication.drugId,
    )

    try:
        ctx = request.userContext
        candidate = request.candidateMedication
        med_name = candidate.customName or candidate.drugId or "unknown"

        llm = get_llm_client()
        log.info("llm_validation_called", user_id=ctx.userId, candidate=med_name)

        drug_html = None
        if candidate.drugId:
            drug_info = await get_drug_by_id(str(candidate.drugId))
            if drug_info:
                drug_html = drug_info.get("html")

        system_prompt = (
            "Ты — медицинский ассистент по безопасности лекарств. "
            "На вход ты получаешь JSON с препаратом, его дозой, HTML-страницей из базы, "
            "и профилем пользователя. Твоя задача — вернуть ТОЛЬКО корректный JSON без markdown и без пояснений вне JSON. "
            "Формат ответа: {\"status\":\"ok|warning|danger\",\"warnings\":[...],\"blockers\":[...],\"metadata\":{...}}. "
            "Если всё безопасно — status=ok, warnings=[], blockers=[]. "
            "Если есть риск или противопоказание — status=warning или danger и добавь понятные причины. "
            "Учитывай аллергию, дозу, хронические заболевания, взаимодействия и инструкции."
        )

        user_context_snip = {
            "userId": ctx.userId,
            "birthDate": getattr(ctx, "birthDate", None),
            "heightCm": getattr(ctx, "heightCm", None),
            "weightKg": getattr(ctx, "weightKg", None),
            "bloodType": getattr(ctx, "bloodType", None),
            "diagnoses": [
                {"name": d.name, "diagnosedAt": getattr(d, "diagnosedAt", None)}
                for d in ctx.diagnoses
            ],
            "allergies": [
                {"allergen": a.allergen, "reaction": getattr(a, "reaction", None)}
                for a in ctx.allergies
            ],
            "contextDegraded": getattr(ctx, "contextDegraded", False),
            "contextWarnings": list(getattr(ctx, "contextWarnings", []) or []),
            "activeMedications": [
                {
                    "tradeName": m.tradeName,
                    "internationalName": m.internationalName,
                    "doseAmount": m.doseAmount,
                    "doseUnit": m.doseUnit,
                    "instructions": m.instructions,
                }
                for m in ctx.activeMedications
            ],
        }

        payload_for_llm = {
            "candidate": {
                "drugId": str(candidate.drugId) if candidate.drugId else None,
                "customName": candidate.customName,
                "doseAmount": candidate.doseAmount,
                "doseUnit": candidate.doseUnit,
                "instructions": candidate.instructions,
                "startDate": candidate.startDate,
                "endDate": candidate.endDate,
            },
            "userContext": user_context_snip,
        }
        if drug_html:
            payload_for_llm["drugHtml"] = drug_html[:30000]

        log.info(
            "llm_validation_payload_ready",
            user_id=ctx.userId,
            candidate=med_name,
            has_html=bool(drug_html),
            payload_chars=len(json.dumps(payload_for_llm, ensure_ascii=False)),
        )

        llm_response = await llm.chat(
            messages=[{"role": "user", "content": json.dumps(payload_for_llm, ensure_ascii=False)}],
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=1000,
        )

        try:
            parsed = json.loads(llm_response)
        except Exception as exc:
            log.error("llm_validation_parse_failed", error=str(exc), raw=llm_response[:2000])
            return MedicationSafetyResponse(
                status="unavailable",
                warnings=[],
                blockers=[],
                metadata={"error": "LLM returned invalid JSON", "raw": llm_response[:2000]},
            )

        status_value = str(parsed.get("status") or "unavailable").strip().lower()
        warnings = parsed.get("warnings") or []
        blockers = parsed.get("blockers") or []
        metadata = parsed.get("metadata") or {}

        if status_value not in {"ok", "warning", "danger", "unavailable"}:
            status_value = "unavailable"

        return MedicationSafetyResponse(
            status=status_value,
            warnings=warnings,
            blockers=blockers,
            metadata=metadata,
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

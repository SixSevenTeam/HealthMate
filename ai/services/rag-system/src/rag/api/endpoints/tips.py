"""Эндпоинты AI-подсказок для dashboard.

- POST /ai/tips/generate: генерирует короткие персональные советы и подсказки.
- POST /ai/tips/invalidate: сбрасывает кеш подсказок пользователя.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel, Field, ValidationError
from pydantic import BaseModel, Field, ValidationError, model_validator

from rag.core.config import settings
from rag.core.llm_client import get_llm_client

log = structlog.get_logger()
router = APIRouter()

_TIPS_PREFIX = "tips:"
_redis_client: aioredis.Redis | None = None


def _extract_json_from_llm_response(response: str, max_attempts: int = 3) -> dict[str, Any] | None:
    """Извлекает JSON из ответа LLM, даже если он обёрнут в текст."""
    response = response.strip()
    

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    

    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    

    match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    

    log.warning("json_extraction_failed", response_length=len(response), response_start=response[:100])
    return None


class TipsAdherenceItem(BaseModel):
    tradeName: str = Field(default="", alias="tradeName")
    totalScheduled: int = Field(default=0, alias="totalScheduled")
    totalTaken: int = Field(default=0, alias="totalTaken")
    adherencePercent: float = Field(default=0.0, alias="adherencePercent")
    missedDates: list[str] = Field(default_factory=list, alias="missedDates")
    model_config = {"populate_by_name": True}


def _normalize_date(value: Any) -> str | None:
    """Безопасно преобразует дату из строки или списка [год, месяц, день] в строку 'YYYY-MM-DD'."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:

            return f"{int(value[0]):04d}-{int(value[1]):02d}-{int(value[2]):02d}"
        except (ValueError, TypeError):
            pass
    return str(value)


class TipsRequest(BaseModel):
    userId: str = Field(alias="userId")
    fromDate: str | None = Field(default=None, alias="from")
    toDate: str | None = Field(default=None, alias="to")
    scope: str = Field(default="active")
    userContext: dict[str, Any] = Field(default_factory=dict, alias="userContext")
    overallAdherence: float = Field(default=0.0, alias="overallAdherence")
    totalScheduled: int = Field(default=0, alias="totalScheduled")
    totalTaken: int = Field(default=0, alias="totalTaken")
    adherence: list[TipsAdherenceItem] = Field(default_factory=list)
    model_config = {"populate_by_name": True}

    @model_validator(mode='before')
    @classmethod
    def normalize_dates_before_validation(cls, data: Any) -> Any:
        """Нормализует даты до того, как Pydantic начнёт строгую проверку типов."""
        if isinstance(data, dict):
            if "from" in data:
                data["from"] = _normalize_date(data["from"])
            elif "fromDate" in data:
                data["fromDate"] = _normalize_date(data["fromDate"])

            if "to" in data:
                data["to"] = _normalize_date(data["to"])
            elif "toDate" in data:
                data["toDate"] = _normalize_date(data["toDate"])
        return data


class TipsResponse(BaseModel):
    insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source: str = "generated"


class InvalidateTipsRequest(BaseModel):
    userId: str = Field(alias="userId")
    reason: str | None = None
    model_config = {"populate_by_name": True}


class InvalidateTipsResponse(BaseModel):
    deleted: int


def _parse_tips_request(payload: dict[str, Any]) -> TipsRequest:
    try:
        return TipsRequest.model_validate(payload)
    except ValidationError as exc:
        log.warning(
            "tips_request_validation_failed",
            errors=exc.errors(),
            payload_keys=sorted(payload.keys()),
        )

        user_id = payload.get("userId") or payload.get("user_id") or ""
        adherence_payload = payload.get("adherence") or []
        if not isinstance(adherence_payload, list):
            adherence_payload = []

        parsed_adherence: list[TipsAdherenceItem] = []
        for item in adherence_payload:
            if not isinstance(item, dict):
                continue
            try:
                parsed_adherence.append(TipsAdherenceItem.model_validate(item))
            except ValidationError:
                continue


        raw_from = payload.get("from") or payload.get("fromDate")
        raw_to = payload.get("to") or payload.get("toDate")

        return TipsRequest(
            userId=str(user_id),
            fromDate=_normalize_date(raw_from),
            toDate=_normalize_date(raw_to),
            scope=str(payload.get("scope") or "active"),
            userContext=payload.get("userContext") or payload.get("user_context") or {},
            overallAdherence=float(payload.get("overallAdherence") or 0.0),
            totalScheduled=int(payload.get("totalScheduled") or 0),
            totalTaken=int(payload.get("totalTaken") or 0),
            adherence=parsed_adherence,
        )

async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _safe_profile_summary(user_context: dict[str, Any]) -> str:
    diagnoses = [d.get("name", "") for d in user_context.get("diagnoses", []) if isinstance(d, dict)]
    allergies = [a.get("allergen", "") for a in user_context.get("allergies", []) if isinstance(a, dict)]
    meds = [m.get("tradeName") or m.get("internationalName") or "" for m in user_context.get("activeMedications", []) if isinstance(m, dict)]

    height = user_context.get("heightCm")
    weight = user_context.get("weightKg")

    return (
        f"Диагнозы: {', '.join([x for x in diagnoses if x]) or 'не указаны'}\n"
        f"Аллергии: {', '.join([x for x in allergies if x]) or 'не указаны'}\n"
        f"Активные лекарства: {', '.join([x for x in meds if x]) or 'не указаны'}\n"
        f"Рост/вес: {height or 'н/д'} см / {weight or 'н/д'} кг"
    )


def _build_cache_key(request: TipsRequest) -> str:
    cache_payload = {
        "scope": request.scope,
        "from": request.fromDate,
        "to": request.toDate,
        "userContext": request.userContext,
        "overallAdherence": round(request.overallAdherence, 2),
        "totalScheduled": request.totalScheduled,
        "totalTaken": request.totalTaken,
        "adherence": [item.model_dump(by_alias=True) for item in request.adherence],
    }
    raw = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{_TIPS_PREFIX}{request.userId}:{digest}"


def _rule_based_fallback(request: TipsRequest) -> TipsResponse:
    total_scheduled = max(request.totalScheduled, 0)
    total_taken = max(request.totalTaken, 0)
    overall = round(request.overallAdherence, 2)

    low_count = sum(1 for item in request.adherence if item.adherencePercent < 80)
    missed_count = sum(1 for item in request.adherence if item.missedDates)

    insights = [
        f"За период вы приняли {total_taken} из {total_scheduled} назначений ({overall}%).",
    ]

    if overall >= 80:
        insights.append("Хороший темп приема, продолжайте в том же режиме.")
    elif overall >= 50:
        insights.append("Есть заметные пропуски, стоит усилить режим напоминаний.")
    else:
        insights.append("Сейчас много пропусков, давайте упростим схему и закрепим время приема.")

    if low_count > 0:
        insights.append(f"Ниже целевого уровня 80% сейчас {low_count} препарат(а).")
    if missed_count > 0:
        insights.append(f"Пропуски есть по {missed_count} препарат(у/ам).")

    recommendations = []
    if overall < 80:
        recommendations.append("Привяжите прием к ежедневному действию: завтрак, обед или ужин.")
        recommendations.append("Поставьте два напоминания: в момент приема и повтор через 20 минут.")
    else:
        recommendations.append("Сохраняйте фиксированное время приема, это поддерживает стабильный эффект.")

    if missed_count > 0:
        recommendations.append("Проверьте календарь приема и закройте ближайшие пропуски по назначению врача.")

    if not recommendations:
        recommendations = [
            "Пейте достаточно воды в течение дня.",
            "Старайтесь хорошо высыпаться и придерживаться режима сна.",
            "Принимайте лекарства строго по схеме врача.",
        ]

    return TipsResponse(
        insights=insights[:3],
        recommendations=recommendations[:3],
        source="fallback",
    )


async def _generate_with_llm(request: TipsRequest) -> TipsResponse:
    llm = get_llm_client()

    adherence_lines = []
    for item in request.adherence[:10]:
        adherence_lines.append(
            f"- {item.tradeName}: принято {item.totalTaken} из {item.totalScheduled}, "
            f"{round(item.adherencePercent, 2)}%, пропусков: {len(item.missedDates)}"
        )

    prompt = (
        "Ты медицинский ассистент HealthMate. "
        "Верни только JSON без markdown и без пояснений.\n"
        "Язык: русский. Тон: простой человеческий, короткие фразы.\n"
        "Сделай 1-3 пункта insights и 1-3 пункта recommendations.\n"
        "Insights: объясни, что человек выпил и что пропустил.\n"
        "Recommendations: разумные советы по приему лекарств."
        "Если данных мало - добавь общие советы (вода, сон, режим).\n"
        "Формат строго:\n"
        "{\"insights\": [\"...\"], \"recommendations\": [\"...\"]}\n\n"
        f"Период: {request.fromDate or '-'} - {request.toDate or '-'}\n"
        f"Общая приверженность: {round(request.overallAdherence, 2)}%\n"
        f"Принято/назначено: {request.totalTaken}/{request.totalScheduled}\n"
        f"Профиль пользователя:\n{_safe_profile_summary(request.userContext)}\n"
        f"Лекарства и прием:\n{chr(10).join(adherence_lines) or '- нет данных -'}\n"
    )

    response_text = await llm.chat(
        messages=[{"role": "user", "content": "Сформируй персональные подсказки"}],
        system_prompt=prompt,
        temperature=0.2,
        max_tokens=500,
    )

    parsed = _extract_json_from_llm_response(response_text)
    if not parsed:
        log.error("tips_llm_parse_failed", response_length=len(response_text), response_start=response_text[:200])
        raise ValueError(f"Failed to parse LLM response as JSON: {response_text[:500]}")

    insights = [str(x).strip() for x in parsed.get("insights", []) if str(x).strip()]
    recommendations = [str(x).strip() for x in parsed.get("recommendations", []) if str(x).strip()]

    log.info(
        "tips_llm_payload_parsed",
        insights_count=len(insights),
        recommendations_count=len(recommendations),
        user_id=request.userId,
    )

    return TipsResponse(
        insights=insights[:3],
        recommendations=recommendations[:3],
        source="generated",
    )


@router.post(
    "/ai/tips/generate",
    response_model=TipsResponse,
    status_code=status.HTTP_200_OK,
    summary="Генерация персональных подсказок для dashboard",
)
async def generate_tips(payload: dict[str, Any]) -> TipsResponse:
    request = _parse_tips_request(payload)
    log.info(
        "tips_generate_called",
        user_id=request.userId,
        scope=request.scope,
        total_scheduled=request.totalScheduled,
        total_taken=request.totalTaken,
    )
    key = _build_cache_key(request)
    redis = await _get_redis()

    cached = await redis.get(key)
    if cached:
        payload = json.loads(cached)
        payload.pop("source", None)
        log.info("tips_cache_hit", user_id=request.userId, cache_key=key)
        return TipsResponse(**payload, source="cache")

    log.info("tips_cache_miss", user_id=request.userId, cache_key=key)

    try:
        result = await _generate_with_llm(request)
        log.info("tips_generated_with_llm", user_id=request.userId)
    except Exception as exc:
        log.warning("tips_generation_failed", error=str(exc), user_id=request.userId)
        result = _rule_based_fallback(request)

    if not result.insights:
        result = _rule_based_fallback(request)
    if not result.recommendations:
        fallback = _rule_based_fallback(request)
        result.recommendations = fallback.recommendations

    await redis.setex(
        key,
        settings.tips_cache_ttl_seconds,
        json.dumps(result.model_dump(), ensure_ascii=False),
    )
    log.info("tips_cache_saved", user_id=request.userId, cache_key=key, source=result.source)
    return result


@router.post(
    "/ai/tips/invalidate",
    response_model=InvalidateTipsResponse,
    status_code=status.HTTP_200_OK,
    summary="Инвалидация кеша подсказок пользователя",
)
async def invalidate_tips(payload: dict[str, Any]) -> InvalidateTipsResponse:
    request = InvalidateTipsRequest.model_validate(payload)
    redis = await _get_redis()
    pattern = f"{_TIPS_PREFIX}{request.userId}:*"
    deleted = 0
    found = []
    async for key in redis.scan_iter(match=pattern, count=200):
        found.append(key)
        deleted += await redis.delete(key)

    sample = found if len(found) <= 20 else found[:20]
    log.info(
        "tips_cache_invalidated",
        user_id=request.userId,
        reason=request.reason,
        deleted=deleted,
        matched_count=len(found),
        sample_keys=sample,
    )

    return InvalidateTipsResponse(deleted=deleted)

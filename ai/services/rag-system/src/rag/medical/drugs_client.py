"""Client для поиска препаратов в Java-бэкенде.

Позволяет искать препарат по фрагменту строки и возвращать первый релевантный
результат с полем `id`, `tradeName` и флагом `hasMedia`.
"""

from __future__ import annotations

import os
import re
import structlog
from typing import Any

import httpx

from rag.core.config import settings

log = structlog.get_logger()


def _backend_base_urls() -> list[str]:
    """Возвращает список backend base URL в порядке приоритета.

    В docker-compose `rag-system` работает в отдельном контейнере, поэтому
    `localhost:8080` может указывать не на Java backend. Мы пробуем несколько
    вариантов и берём первый живой.
    """
    candidates: list[str] = []
    for value in (
        os.environ.get("BACKEND_INTERNAL_URL"),
        os.environ.get("BACKEND_URL"),
        getattr(settings, "backend_internal_url", None),
        settings.backend_url,
        "http://backend:8080",
        "http://host.docker.internal:8080",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ):
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def _backend_headers() -> dict[str, str]:
    """Собирает заголовки для запросов к Java backend."""
    headers: dict[str, str] = {}
    token = (settings.backend_auth_token or "").strip()
    header_name = (settings.backend_auth_header_name or "Authorization").strip() or "Authorization"

    if token:
        headers[header_name] = token

    return headers


async def search_drug_by_name(query: str) -> dict | None:
    """Ищет препарат в backend (/healthmate/api/drugs/search?q=...). Возвращает первый совпавший объект или None."""
    if not query or len(query.strip()) < 2:
        return None

    url = f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/search"
    params = {"q": query}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, params=params, headers=_backend_headers())
            if r.status_code != 200:
                log.debug(
                    "drug_search_non_200",
                    url=url,
                    status=r.status_code,
                    response_preview=r.text[:500],
                )
                return None
            data = r.json()
            results = data.get("results") or []
            if not results:
                return None
            first = results[0]
            return {
                "id": first.get("id"),
                "tradeName": first.get("tradeName"),
                "internationalName": first.get("internationalName"),
                "hasMedia": bool(first.get("hasMedia", False)),
            }
    except Exception as exc:
        log.debug("drug_search_error", error=str(exc), query=query)
        return None


def extract_candidate_terms(text: str, max_terms: int = 20) -> list[str]:
    """Простой экстрактор кандидатов — слова/фразы с длиной >=4, ограничение на количество."""
    # Поддерживаем многословные названия (до 3 слов)
    tokens = re.findall(r"[\w\-А-Яа-яЁё]{4,}", text)
    seen: set[str] = set()
    res: list[str] = []
    for t in tokens:
        norm = t.strip()
        if not norm:
            continue
        if norm.lower() in seen:
            continue
        seen.add(norm.lower())
        res.append(norm)
        if len(res) >= max_terms:
            break
    return res


async def search_drugs(query: str, limit: int = 20) -> list[dict]:
    """Ищет препараты в backend и возвращает список результатов (up to limit).

    Возвращаемые объекты нормализуем до полей: id, tradeName, indications,
    contraindications, snippet, hasMedia.
    """
    if not query or len(query.strip()) < 2:
        return []

    url = f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/search"
    params = {"q": query, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params, headers=_backend_headers())
            if r.status_code != 200:
                log.debug(
                    "drugs_search_non_200",
                    url=url,
                    status=r.status_code,
                    response_preview=r.text[:500],
                )
                return []
            data = r.json()
            results = data.get("results") or []
            out: list[dict] = []
            for item in results[:limit]:
                out.append(
                    {
                        "id": item.get("id"),
                        "tradeName": item.get("tradeName") or item.get("name") or "",
                        "indications": item.get("indications") or item.get("indication") or "",
                        "contraindications": item.get("contraindications") or "",
                        "snippet": (item.get("indications") or item.get("summary") or "")[:300],
                        "hasMedia": bool(item.get("hasMedia", False)),
                    }
                )
            return out
    except Exception as exc:
        log.debug("drugs_search_error", error=str(exc), query=query)
        return []


async def get_drug_by_id(drug_id: str) -> dict | None:
    """Возвращает полную HTML информацию о препарате по id через backend API.
    
    Запрашивает /healthmate/api/drugs/{drugId}/details которая возвращает HTML с полными данными:
    показания, противопоказания, состав, дозировку, побочные эффекты и т.д.
    """
    if not drug_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            last_error_preview = None
            for base_url in _backend_base_urls():
                base = base_url.rstrip("/")
                details_url = f"{base}/healthmate/api/drugs/{drug_id}/details"
                try:
                    r = await client.get(details_url, headers=_backend_headers())
                except Exception as exc:
                    log.debug("drug_details_request_error", base_url=base_url, drug_id=drug_id, error=str(exc))
                    continue

                if r.status_code != 200:
                    last_error_preview = r.text[:500]
                    log.debug(
                        "drug_details_non_200",
                        base_url=base_url,
                        url=details_url,
                        status=r.status_code,
                        drug_id=drug_id,
                        response_preview=last_error_preview,
                    )
                    continue

                html_content = r.text
                meta = None
                meta_url = f"{base}/healthmate/api/drugs/{drug_id}"
                try:
                    rm = await client.get(meta_url, headers=_backend_headers())
                    if rm.status_code == 200:
                        meta = rm.json()
                    else:
                        log.debug(
                            "drug_metadata_non_200",
                            base_url=base_url,
                            url=meta_url,
                            status=rm.status_code,
                            drug_id=drug_id,
                            response_preview=rm.text[:500],
                        )
                except Exception as exc:
                    log.debug("drug_metadata_error", base_url=base_url, error=str(exc), drug_id=drug_id)

                out = {
                    "id": drug_id,
                    "html": html_content,
                    "html_length": len(html_content),
                }
                if meta:
                    out.update(
                        {
                            "tradeName": meta.get("tradeName") or meta.get("name") or "",
                            "internationalName": meta.get("internationalName"),
                            "doseUnit": meta.get("doseUnit"),
                            "minDose": meta.get("minDose"),
                            "maxDose": meta.get("maxDose"),
                            "hasMedia": bool(meta.get("hasMedia", False)),
                        }
                    )

                log.debug(
                    "drug_details_loaded",
                    base_url=base_url,
                    drug_id=drug_id,
                    html_length=len(html_content),
                    trade_name=out.get("tradeName"),
                )
                return out

            log.debug(
                "drug_details_all_candidates_failed",
                drug_id=drug_id,
                backend_candidates=_backend_base_urls(),
                last_error_preview=last_error_preview,
            )
            return None
    except Exception as exc:
        log.debug("drug_details_error", error=str(exc), drug_id=drug_id)
        return None


async def get_drugs_by_ids(drug_ids: list[str]) -> dict[str, dict | None]:
    """Получает полные данные для нескольких препаратов параллельно.
    
    Args:
        drug_ids: Список UUID препаратов из payload чанков.
    
    Returns:
        Словарь {drug_id -> полные данные препарата или None}.
    """
    import asyncio
    
    if not drug_ids:
        return {}
    
    # Убираем дубликаты и None
    unique_ids = list(set(id for id in drug_ids if id))
    
    log.info(f"fetching_full_drugs", count=len(unique_ids), drug_ids=unique_ids)
    
    # Параллельно запрашиваем все препараты
    tasks = [get_drug_by_id(drug_id) for drug_id in unique_ids]
    results = await asyncio.gather(*tasks)
    
    drugs_by_id = {drug_id: result for drug_id, result in zip(unique_ids, results)}
    
    succeeded = sum(1 for v in drugs_by_id.values() if v is not None)
    log.info(f"fetched_full_drugs", succeeded=succeeded, total=len(unique_ids))
    
    return drugs_by_id

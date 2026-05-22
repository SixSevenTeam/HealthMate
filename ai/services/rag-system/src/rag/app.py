"""FastAPI application entrypoint for the HealthMate AI service.

This app serves the Java-facing chat and medication validation endpoints,
plus the internal query/document API. The one-shot dataset indexer stays in
`src/main.py` and is not used for the runtime container.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from rag.api.router import api_router, chat_router
from rag.core.config import settings
from rag.core.embeddings import get_embedding_service
from rag.core.logger import setup_logging
from rag.retrieval.retriever import get_retriever

setup_logging()
log = structlog.get_logger()

app = FastAPI(
    title="HealthMate AI Service",
    version=settings.service_version,
    description="Internal AI service for chat, anamnesis, and medication validation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def internal_key_guard(request: Request, call_next):
    """Protect internal API routes with a shared header key.

    Health and OpenAPI routes remain public for container probes and debugging.
    If no key is configured, the guard is effectively disabled for local dev.
    """
    path = request.url.path
    is_protected = path.startswith("/ai") or path.startswith("/api/v1")
    is_public = path in {"/health", "/", "/docs", "/openapi.json", "/redoc"}

    if is_protected and not is_public and settings.internal_api_key:
        provided = request.headers.get("X-Internal-Key", "")
        if provided != settings.internal_api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing internal API key"},
            )

    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name, "version": settings.service_version}


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


app.include_router(api_router)
app.include_router(chat_router)


@app.on_event("startup")
async def warmup_embeddings() -> None:
    """Preload embedding model and BM25 index at startup to avoid first-request stall."""
    started = time.monotonic()
    try:
        embedding_service = get_embedding_service()
        await embedding_service.embed_text("warmup")
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info("embedding_warmup_complete", elapsed_ms=elapsed_ms)
    except Exception as exc:
        log.warning("embedding_warmup_failed", error=str(exc))

    try:
        retriever = get_retriever()
        await retriever._ensure_sparse_index()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info("bm25_warmup_complete", elapsed_ms=elapsed_ms)
    except Exception as exc:
        log.warning("bm25_warmup_failed", error=str(exc))

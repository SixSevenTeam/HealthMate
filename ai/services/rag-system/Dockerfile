# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu torch==2.5.1+cpu

COPY src ./src/
RUN --mount=type=cache,target=/root/.cache/pip pip install .

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src ./src/

RUN mkdir -p /tmp/jsn-rag

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --no-log-init appuser && \
    chown -R appuser:appuser /tmp/jsn-rag /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200" || exit 1

CMD ["uvicorn", "rag.app:app", "--host", "0.0.0.0", "--port", "8000"]

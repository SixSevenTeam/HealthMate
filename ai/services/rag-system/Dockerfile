FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src ./src/
COPY alembic ./alembic/

RUN mkdir -p /tmp/jsn-rag

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --no-log-init appuser && \
    chown -R appuser:appuser /tmp/jsn-rag /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200" || exit 1

CMD ["python", "-m", "main"]

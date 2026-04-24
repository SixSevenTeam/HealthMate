FROM python:3.11-slim-bookworm

WORKDIR /app

# Обновляем системные пакеты для устранения известных уязвимостей
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src ./src/

# Каталог для временных файлов документов
RUN mkdir -p /tmp/doc-parser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Запуск от непривилегированного пользователя
RUN useradd --create-home --no-log-init appuser && \
    chown -R appuser:appuser /tmp/doc-parser
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import docparser.core; print('ok')" || exit 1

CMD ["python", "-m", "src.main"]

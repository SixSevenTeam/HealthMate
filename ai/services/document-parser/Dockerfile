FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для PyMuPDF
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libmupdf-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src/

# Каталог для временных PDF
RUN mkdir -p /tmp/doc-parser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]

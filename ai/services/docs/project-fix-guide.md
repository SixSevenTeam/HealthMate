# Фикс структуры проекта и импортов

## Проблема
Python не видит импорты типа `from core.config import settings` из-за неправильной настройки пакетов.

## Решение

### Вариант 1: Editable Install (Рекомендуемый для разработки)

#### Для document-parser:

```bash
cd D:\VSU\project\HealthMate\backend\health-consultation-platform\services\document-parser

# Установить в editable режиме
pip install -e .
```

#### Для rag-system:

```bash
cd D:\VSU\project\HealthMate\backend\health-consultation-platform\services\rag-system

# Установить в editable режиме
pip install -e .
```

**После этого импорты будут работать так:**

```python
# В файлах src/infrastructure/kafka/producer.py
from docparser.core import settings  # ✅ Работает
from docparser.domain.models import OutgoingEvent  # ✅ Работает
```

---

### Вариант 2: Переписать импорты на абсолютные (если не хочешь устанавливать)

#### В document-parser:

Меняешь все импорты на:

```python
# Было:
from docparser.core import settings

# Стало:
from src.core.config import settings
```

Но для этого нужно добавить в начало каждого запускаемого файла (main.py, consumer.py):

```python
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))
```

---

## Для .gitignore

Добавь в **корневой** `.gitignore` (в `health-consultation-platform/`):

```gitignore
# Environment variables
**/.env
**/.env.*
!**/.env.example

# Python
**/__pycache__/
**/*.py[cod]
**/*$py.class
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/

# IDE
**/.vscode/
**/.idea/
**/*.swp
**/*.swo
**/DS_Store

# Virtual environments
**/venv/
**/.venv/
**/env/

# Build artifacts
**/build/
**/dist/
**/*.egg-info/
```

---

## Что положить в каждый сервис

### document-parser/

Файлы которые нужно добавить:

1. **pyproject.toml** (см. ниже)
2. **setup.py** (см. ниже)
3. **.env.example** - пример конфигурации

### rag-system/

Файлы которые нужно добавить:

1. **pyproject.toml** (см. ниже)
2. **setup.py** (см. ниже)  
3. **.env.example** - пример конфигурации

---

## Про документ с контрактами

Создай файл `docs/API_CONTRACTS.md` в корне платформы:

```markdown
# API Contracts между сервисами

## Document Parser → RAG System

### Kafka Topic: `document.parsed`

**Событие**: Документ распарсен и готов к embedding

```json
{
  "document_id": "doc-uuid-123",
  "s3_url": "s3://bucket/parsed/doc-uuid-123.json",
  "metadata": {
    "title": "Инструкция по применению Парацетамола",
    "category": "medication",
    "language": "ru",
    "page_count": 5,
    "parsed_at": "2026-04-19T15:30:00Z"
  },
  "structure": {
    "type": "hierarchical",
    "format": "tree_json",
    "root_sections": ["Состав", "Показания", "Противопоказания", "Дозировка"]
  }
}
```

### RAG System → Document Parser

**Kafka Topic**: `document.status`

**Событие**: Статус обработки документа

```json
{
  "document_id": "doc-uuid-123",
  "status": "embedded" | "failed" | "processing",
  "chunks_created": 42,
  "vectors_stored": 42,
  "error_message": null,
  "processed_at": "2026-04-19T15:32:00Z"
}
```

## Java Service → RAG System

### REST API: POST /api/v1/query

**Request**:

```json
{
  "user_id": "user-uuid-456",
  "session_id": "session-uuid-789",
  "query": "болит голова второй день",
  "user_profile": {
    "allergies": ["aspirin"],
    "chronic_conditions": ["гипертония"],
    "current_medications": [
      {
        "name": "лизиноприл",
        "dosage": "10mg",
        "frequency": "1x daily"
      }
    ]
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "болит голова второй день",
      "timestamp": "2026-04-19T10:00:00Z"
    }
  ]
}
```

**Response**:

```json
{
  "request_id": "req-uuid-abc",
  "stage": "anamnesis_collection",
  "response_type": "clarifying_question",
  "content": {
    "message": "Какой характер боли? (пульсирующая, давящая, острая)",
    "options": ["пульсирующая", "давящая", "острая", "другое"]
  },
  "next_action": "await_user_response"
}
```
```

---

## Структура .env файлов

### document-parser/.env.example

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_INPUT_TOPIC=document.uploaded
KAFKA_OUTPUT_TOPIC=document.parsed
KAFKA_STATUS_TOPIC=document.status

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
MINIO_USE_SSL=false

# Logging
LOG_LEVEL=INFO
```

### rag-system/.env.example

```env
# LLM
DEEPSEEK_API_KEY=your_deepseek_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7

# Embeddings
EMBEDDING_PROVIDER=openai  # or "cohere" or "huggingface"
OPENAI_API_KEY=your_openai_key_here
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=1536

# Vector Database
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=medical_documents

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis (для кеширования)
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_INPUT_TOPIC=document.parsed
KAFKA_STATUS_TOPIC=document.status

# API
API_HOST=0.0.0.0
API_PORT=8001
API_WORKERS=4

# Logging
LOG_LEVEL=INFO
STRUCTLOG_DEV_MODE=true
```

---

## Команды для запуска

### 1. Установка зависимостей

```bash
# document-parser
cd services/document-parser
pip install -e .

# rag-system  
cd services/rag-system
pip install -e .
```

### 2. Запуск инфраструктуры

```bash
cd services/rag-system
docker-compose up -d
```

### 3. Запуск сервисов

```bash
# Терминал 1: Document Parser Consumer
cd services/document-parser
python src/infrastructure/kafka/consumer.py

# Терминал 2: RAG System Consumer
cd services/rag-system
python -m src.infrastructure.kafka.consumer

# Терминал 3: RAG API
cd services/rag-system
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

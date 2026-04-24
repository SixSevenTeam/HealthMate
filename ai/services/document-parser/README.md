# document-parser

Микросервис парсинга медицинских документов платформы HealthMate.
Читает HTM/HTML-файлы инструкций к лекарствам из MinIO, конвертирует их в Markdown
и строит иерархическое JSON-дерево для дальнейшей обработки RAG-системой.

---

## Архитектура

```
Java Backend
    │  Kafka: json-outgoing
    │  Событие: { id, minIoBucket, filePath }
    ▼
KafkaEventConsumer
    │
    ▼
DocumentProcessingService  ← главный оркестратор
    │
    ├── MinioStorage         скачивает HTM-файл из MinIO
    │
    ├── Processor            HTM → очищенный Markdown
    │       ├── charset-normalizer   (определение кодировки cp1251/utf-8)
    │       ├── BeautifulSoup/lxml   (парсинг HTML)
    │       └── html2text            (конвертация в Markdown)
    │
    ├── MarkdownTreeBuilder  Markdown → иерархический JSON
    │
    ├── MinioStorage         сохраняет JSON-результат
    │
    └── KafkaEventProducer
            ├── Kafka: document.status   (PROCESSING / MARKDOWN_READY / FAILED)
            └── Kafka: json-outgoing     (OutgoingEvent → RAG-сервис)
```

### Структура пакетов

```
src/
├── main.py                                   точка входа
├── utils.py                                  утилиты (MD5/Base64)
└── docparser/
    ├── core/
    │   ├── __init__.py                       Settings (pydantic-settings)
    │   └── logger.py                         structlog setup
    ├── domain/
    │   └── __init__.py                       IncomingEvent, OutgoingEvent, ProcessedDocument
    ├── application/
    │   └── __init__.py                       DocumentProcessingService
    └── infrastructure/
        ├── kafka/
        │   ├── consumer.py                   KafkaEventConsumer (At-Least-Once)
        │   └── producer.py                   KafkaEventProducer
        ├── minio/
        │   └── __init__.py                   MinioStorage (tenacity retry)
        └── pars/
            ├── __init__.py                   Processor (HTML → Markdown)
            └── tree_builder.py               MarkdownTreeBuilder (Markdown → JSON)
```

---

## Поток сообщений

### Входящее событие (Java → document-parser)

**Kafka topic:** `json-outgoing`

```json
{
  "id": "doc-uuid-123",
  "minIoBucket": "raw-documents",
  "filePath": "paracetamol.htm"
}
```

> **Важно:** поля используют camelCase (wire-формат Java).
> Внутри сервиса они маппятся в snake_case: `minio_bucket`, `file_path`.

### Статусные события (document-parser → Java)

**Kafka topic:** `document.status`

| Статус | Когда отправляется |
|--------|--------------------|
| `PROCESSING` | До скачивания файла, после конвертации, перед сохранением |
| `MARKDOWN_READY` | Документ успешно обработан и сохранён |
| `FAILED` | Любая ошибка в pipeline |

```json
{
  "document_id": "doc-uuid-123",
  "status": "PROCESSING",
  "message": "Парсинг HTM-документа в Markdown...",
  "timestamp": "2026-04-21T12:00:00Z"
}
```

### Итоговое событие (document-parser → RAG-сервис)

**Kafka topic:** `json-outgoing`

```json
{
  "document_id": "doc-uuid-123",
  "result_bucket": "processed-json-doc",
  "result_file": "doc-uuid-123.json",
  "status": "processed"
}
```

---

## Pipeline обработки файла

```
1. Idempotency-check
   └── Если JSON уже есть в MinIO → отправить MARKDOWN_READY + OutgoingEvent → выйти

2. Скачивание файла
   └── MinIO: raw-documents/paracetamol.htm → /tmp/doc-parser/{id}.htm

3. Определение кодировки
   └── charset-normalizer: utf-8 / cp1251 / ...

4. Парсинг HTML (BeautifulSoup + lxml)
   └── Удаляем: header, footer, nav, script, style, [class*=toc], [class*=pagenum]

5. Конвертация в Markdown (html2text)
   └── Настройки: body_width=0, ignore_images=True, ignore_tables=False

6. Очистка Markdown
   └── Unicode-мусор → пробел, 3+ пустые строки → 2

7. Построение JSON-дерева (MarkdownTreeBuilder)
   └── # → depth=1, ## → depth=2, ... с вложением через стек

8. Сохранение в MinIO
   └── processed-json-doc/{document_id}.json

9. Kafka-события
   └── MARKDOWN_READY + OutgoingEvent → RAG-сервис
```

### Формат JSON-дерева

```json
{
  "type": "root",
  "heading": { "depth": 0, "title": "Document Root", "page_starts_at": 1 },
  "content": "",
  "children": [
    {
      "type": "section",
      "heading": { "depth": 1, "title": "Показания к применению", "page_starts_at": 1 },
      "content": "Головная боль, жар.",
      "children": [
        {
          "type": "section",
          "heading": { "depth": 2, "title": "Особые группы", "page_starts_at": 1 },
          "content": "Беременность: с осторожностью.",
          "children": []
        }
      ]
    }
  ]
}
```

---

## Конфигурация

Все параметры читаются из переменных окружения или `.env` файла.

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Адрес Kafka-брокера |
| `KAFKA_CONSUMER_GROUP` | `python-group` | Consumer group ID |
| `KAFKA_INPUT_TOPIC` | `json-outgoing` | Topic входящих событий |
| `KAFKA_OUTPUT_TOPIC` | `json-outgoing` | Topic итоговых событий для RAG |
| `KAFKA_STATUS_TOPIC` | `document.status` | Topic статусных событий |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint (host:port) |
| `MINIO_ACCESS_KEY` | `admin` | Access key |
| `MINIO_SECRET_KEY` | `admin12345` | Secret key |
| `MINIO_SECURE` | `false` | TLS для MinIO |
| `MINIO_OUTPUT_BUCKET` | `processed-json-doc` | Корзина для JSON-результатов |
| `TEMP_DIR` | `/tmp/doc-parser` | Каталог для временных файлов |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LOG_FORMAT` | `json` | Формат логов: `json` \| `console` |

---

## Запуск локально

### Предварительные требования

- Python 3.11+
- Kafka (локально или через docker-compose)
- MinIO (локально или через docker-compose)

### Установка и запуск

```bash
cd services/document-parser

# Установка зависимостей
pip install -r requirements.txt

# Скопировать и настроить конфиг
cp .env.example .env
# Отредактировать .env под вашу среду

# Запуск сервиса
python -m src.main
```

### Запуск через Docker

```bash
docker build -t document-parser .
docker run --env-file .env document-parser
```

---

## Тесты

```bash
# Запуск всех тестов с отчётом покрытия
pytest --cov=src --cov-report=term-missing

# Только юнит-тесты
pytest test/unit/

# Только интеграционные тесты
pytest test/integration/

# Проверить покрытие >= 80%
pytest --cov=src --cov-fail-under=80
```

### Структура тестов

```
test/
├── conftest.py                              общие фикстуры (HTM-примеры, event-словари)
├── unit/
│   ├── test_processor.py                   14 тестов: чтение HTM, очистка, кодировки
│   ├── test_tree_builder.py                13 тестов: построение дерева из Markdown
│   ├── test_domain_models.py               9 тестов: Pydantic-модели, алиасы
│   └── test_minio_storage.py               9 тестов: MinIO SDK через моки
└── integration/
    ├── test_document_processing_service.py  10 тестов: полный pipeline с моками
    └── test_kafka_flow.py                   7 тестов: consumer/producer поведение
```

---

## Идемпотентность

Сервис реализует At-Least-Once семантику:

1. **Kafka offset** коммитится только после успешной обработки сообщения.
   При ошибке сообщение будет перечитано при рестарте.
2. **MinIO idempotency check**: перед обработкой сервис проверяет, существует ли
   уже `{document_id}.json` в выходной корзине. Если да — пропускает обработку
   и сразу отправляет `MARKDOWN_READY`.
3. **Невалидные сообщения** (плохой JSON / несоответствие контракту) коммитятся
   как dead-letter, чтобы не блокировать очередь.

---

## Логирование

Используется `structlog` с двумя режимами:

- **`LOG_FORMAT=json`** — machine-readable JSON (продакшн, Kibana/Loki)
- **`LOG_FORMAT=console`** — цветной вывод для разработки

Ключевые события:

| Event | Level | Описание |
|-------|-------|----------|
| `processor_read_failed` | ERROR | Не удалось прочитать файл |
| `document_processing_failed` | ERROR | Любая ошибка pipeline |
| `file_not_found_in_minio` | WARNING | S3Error NoSuchKey |
| `temp_file_cleanup_failed` | WARNING | Ошибка очистки временного файла |
| `minio_unexpected_s3_error` | WARNING | Неожиданная S3Error |
| `encoding_detection_failed` | WARNING | charset-normalizer не определил кодировку |
| `kafka_message_invalid` | WARNING | Невалидное Kafka-сообщение (dead-letter) |
| `document_processed_ok` | INFO | Успешная обработка |
| `kafka_offset_committed` | INFO | Коммит offset после успеха |

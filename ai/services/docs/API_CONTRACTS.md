# API Contracts - Health Consultation Platform

Документ описывает все контракты взаимодействия между сервисами платформы.

---

## 1. Document Parser → RAG System

### Kafka Topic: `document.parsed`

**Описание**: Событие отправляется после успешного парсинга документа. RAG система получает это событие и начинает процесс chunking → embedding → vector storage.

**Схема события**:

```json
{
  "document_id": "doc-uuid-123",
  "s3_url": "s3://documents/parsed/doc-uuid-123.json",
  "metadata": {
    "title": "Инструкция по применению Парацетамола",
    "category": "medication",
    "language": "ru",
    "source_filename": "paracetamol.pars",
    "page_count": 5,
    "parsed_at": "2026-04-19T15:30:00Z",
    "parser_version": "0.1.0"
  },
  "structure": {
    "type": "hierarchical",
    "format": "tree_json",
    "root_sections": ["Состав", "Показания", "Противопоказания", "Дозировка", "Побочные эффекты"],
    "total_nodes": 42,
    "max_depth": 4
  }
}
```

**Поля**:
- `document_id` (string, required): Уникальный идентификатор документа
- `s3_url` (string, required): Путь к распарсенному JSON в S3/MinIO
- `metadata` (object, required): Метаданные документа
  - `title` (string): Заголовок документа
  - `category` (string): Категория (medication, disease, procedure, etc.)
  - `language` (string): Язык документа (ru, en)
  - `source_filename` (string): Оригинальное имя файла
  - `page_count` (int): Количество страниц
  - `parsed_at` (ISO 8601): Временная метка парсинга
  - `parser_version` (string): Версия парсера
- `structure` (object, required): Информация о структуре документа
  - `type` (string): Тип структуры (hierarchical, flat)
  - `format` (string): Формат данных (tree_json)
  - `root_sections` (array[string]): Список корневых разделов
  - `total_nodes` (int): Общее количество узлов в дереве
  - `max_depth` (int): Максимальная глубина иерархии

---

## 2. RAG System → Document Parser

### Kafka Topic: `document.status`

**Описание**: RAG система отправляет статусы обработки документа обратно в document-parser для логирования и мониторинга.

**Схема события**:

```json
{
  "document_id": "doc-uuid-123",
  "status": "embedded",
  "details": {
    "chunks_created": 42,
    "vectors_stored": 42,
    "failed_chunks": 0,
    "processing_duration_ms": 1250
  },
  "error": null,
  "timestamp": "2026-04-19T15:32:15Z"
}
```

**Возможные статусы**:
- `processing`: Документ в процессе обработки
- `embedded`: Успешно создан embedding и сохранён в vector DB
- `partially_embedded`: Часть чанков не удалось обработать
- `failed`: Критическая ошибка при обработке

**Поля**:
- `document_id` (string, required)
- `status` (enum, required): Статус обработки
- `details` (object, optional): Детали обработки
  - `chunks_created` (int): Количество созданных чанков
  - `vectors_stored` (int): Количество сохранённых векторов
  - `failed_chunks` (int): Количество неудачных чанков
  - `processing_duration_ms` (int): Время обработки в миллисекундах
- `error` (object, nullable): Информация об ошибке
  - `code` (string): Код ошибки
  - `message` (string): Сообщение об ошибке
  - `details` (object): Дополнительная информация
- `timestamp` (ISO 8601, required)

---

## 3. Java Service → RAG System

### REST API: `POST /api/v1/query`

**Описание**: Основной endpoint для взаимодействия с RAG системой. Обрабатывает запросы пользователей и управляет диалоговым процессом.

**Request**:

```json
{
  "user_id": "user-uuid-456",
  "session_id": "session-uuid-789",
  "query": "болит голова второй день",
  "user_profile": {
    "age": 45,
    "gender": "female",
    "allergies": ["aspirin", "ibuprofen"],
    "chronic_conditions": [
      {
        "name": "гипертония",
        "diagnosed_at": "2020-03-15",
        "severity": "moderate"
      }
    ],
    "current_medications": [
      {
        "name": "лизиноприл",
        "dosage": "10mg",
        "frequency": "1x daily",
        "started_at": "2020-03-20"
      }
    ]
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "болит голова второй день",
      "timestamp": "2026-04-19T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Какой характер боли? (пульсирующая, давящая, острая)",
      "timestamp": "2026-04-19T10:00:05Z"
    },
    {
      "role": "user",
      "content": "пульсирующая в висках",
      "timestamp": "2026-04-19T10:01:00Z"
    }
  ],
  "metadata": {
    "language": "ru",
    "timezone": "Europe/Moscow",
    "client_version": "1.0.0"
  }
}
```

**Response (Этап 1 - Anamnesis Collection)**:

```json
{
  "request_id": "req-uuid-abc",
  "session_id": "session-uuid-789",
  "stage": "anamnesis_collection",
  "response_type": "clarifying_question",
  "content": {
    "message": "Есть ли у вас сопутствующие симптомы?",
    "options": [
      {
        "id": "nausea",
        "label": "Тошнота"
      },
      {
        "id": "photophobia",
        "label": "Светобоязнь"
      },
      {
        "id": "dizziness",
        "label": "Головокружение"
      },
      {
        "id": "none",
        "label": "Нет дополнительных симптомов"
      }
    ],
    "question_type": "multiple_choice",
    "reasoning": "Дифференциация между мигренью и головной болью напряжения требует уточнения сопутствующих симптомов"
  },
  "context_used": {
    "retrieved_documents": [
      {
        "document_id": "doc-123",
        "chunk_id": "chunk-456",
        "title": "Мигрень: диагностика и лечение",
        "relevance_score": 0.89,
        "snippet": "Пульсирующая головная боль в височной области..."
      }
    ],
    "user_constraints_applied": [
      "allergy_aspirin",
      "medication_lisinopril_interaction_check"
    ]
  },
  "next_action": "await_user_response",
  "metadata": {
    "processing_time_ms": 245,
    "llm_model": "deepseek-chat",
    "llm_tokens_used": 1523,
    "confidence_score": 0.85,
    "questions_asked": 1,
    "max_questions": 3
  }
}
```

**Response (Этап 3 - Recommendation)**:

```json
{
  "request_id": "req-uuid-def",
  "session_id": "session-uuid-789",
  "stage": "recommendation",
  "response_type": "medication_recommendation",
  "content": {
    "diagnosis": {
      "primary": "Вероятная мигрень",
      "confidence": 0.82,
      "reasoning": "Пульсирующая боль в височной области с тошнотой и светобоязнью характерны для мигрени"
    },
    "recommendations": [
      {
        "type": "medication",
        "medication": {
          "name": "Суматриптан",
          "dosage": "50mg",
          "frequency": "при приступе",
          "max_daily_dose": "200mg",
          "form": "таблетки"
        },
        "rationale": "Триптаны эффективны при мигрени. Совместим с лизиноприлом. Нет противопоказаний с учётом профиля.",
        "safety_notes": [
          "Не превышать 200мг в сутки",
          "При отсутствии эффекта в течение 2 часов обратиться к врачу"
        ],
        "priority": 1
      },
      {
        "type": "non_medication",
        "action": "Отдых в тёмном тихом помещении",
        "rationale": "Уменьшает раздражители, усиливающие мигрень",
        "priority": 2
      }
    ],
    "warnings": [
      {
        "type": "contraindication_avoided",
        "message": "Не рекомендуется аспирин из-за аллергии",
        "severity": "high"
      }
    ],
    "when_to_seek_emergency": [
      "Внезапная сильнейшая головная боль",
      "Потеря сознания",
      "Нарушение речи или движений"
    ]
  },
  "context_used": {
    "retrieved_documents": [
      {
        "document_id": "doc-123",
        "title": "Клинические рекомендации: Мигрень",
        "relevance_score": 0.91
      },
      {
        "document_id": "doc-456",
        "title": "Суматриптан: инструкция по применению",
        "relevance_score": 0.87
      }
    ],
    "safety_checks_performed": [
      "allergy_screening",
      "drug_interaction_check",
      "chronic_condition_compatibility"
    ]
  },
  "next_action": "conversation_complete",
  "metadata": {
    "processing_time_ms": 892,
    "llm_model": "deepseek-chat",
    "llm_tokens_used": 3241,
    "confidence_score": 0.82
  }
}
```

---

## 4. RAG System → Java Service

### Webhook (опционально): `POST /api/webhooks/rag-status`

**Описание**: Асинхронное уведомление о завершении длительной обработки (если требуется).

**Request**:

```json
{
  "session_id": "session-uuid-789",
  "event_type": "processing_complete",
  "data": {
    "stage": "recommendation",
    "result": { /* полный ответ как выше */ }
  },
  "timestamp": "2026-04-19T10:05:30Z"
}
```

---

## 5. Управление документами

### REST API: `POST /api/v1/documents/upload`

**Описание**: Инициирует загрузку документа в систему (триггерит Kafka event).

**Request**:

```json
{
  "document_id": "doc-uuid-new",
  "s3_url": "s3://documents/raw/new-medication-guide.pars",
  "metadata": {
    "title": "Новый препарат X",
    "category": "medication",
    "language": "ru"
  }
}
```

**Response**:

```json
{
  "document_id": "doc-uuid-new",
  "status": "queued",
  "estimated_processing_time_seconds": 30,
  "message": "Document queued for processing"
}
```

---

### REST API: `GET /api/v1/documents/{document_id}/status`

**Описание**: Проверка статуса обработки документа.

**Response**:

```json
{
  "document_id": "doc-uuid-new",
  "status": "embedded",
  "progress": {
    "stage": "completed",
    "chunks_processed": 42,
    "total_chunks": 42,
    "percent_complete": 100
  },
  "timestamps": {
    "queued_at": "2026-04-19T15:00:00Z",
    "started_at": "2026-04-19T15:00:02Z",
    "completed_at": "2026-04-19T15:00:35Z"
  }
}
```

---

## Типы данных

### UserProfile

```typescript
interface UserProfile {
  age?: number;
  gender?: "male" | "female" | "other" | "prefer_not_to_say";
  allergies: string[];  // Список аллергенов
  chronic_conditions: ChronicCondition[];
  current_medications: Medication[];
}

interface ChronicCondition {
  name: string;
  diagnosed_at?: string;  // ISO 8601
  severity?: "mild" | "moderate" | "severe";
}

interface Medication {
  name: string;
  dosage: string;
  frequency: string;
  started_at?: string;  // ISO 8601
}
```

### ConversationMessage

```typescript
interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;  // ISO 8601
  metadata?: Record<string, any>;
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `RAG_001` | Документ не найден в vector DB |
| `RAG_002` | Недостаточно контекста для ответа |
| `RAG_003` | Превышен лимит уточняющих вопросов |
| `RAG_004` | Ошибка взаимодействия с LLM |
| `RAG_005` | Критическое противопоказание обнаружено |
| `RAG_006` | Таймаут сбора анамнеза |
| `DOC_001` | Ошибка парсинга документа |
| `DOC_002` | Документ не найден в S3 |
| `DOC_003` | Неподдерживаемый формат документа |

---

## Changelog

| Версия | Дата | Изменения |
|--------|------|-----------|
| 0.1.0 | 2026-04-19 | Первая версия контрактов |

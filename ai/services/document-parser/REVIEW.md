**Project Review**

**Summary**:
- **Scope**: Быстрый ревью кода микросервиса для конвертации PDF → JSON (Kafka + MinIO).
- **High level**: Архитектура понятна и разделена по слоям (application / infrastructure / domain). Основные проблемы — небольшие ошибки импорта/аннотаций, отсутствие CI/tests, безопасность конфигурации, мелкие проблемы с управлением жизненным циклом компонентов и контейнеризацией.

**What Is Wrong**:
- **Missing postponed annotations**: `src/application/service.py` использует тип `MarkdownTreeBuilder` в аннотациях, но не импортирует `from __future__ import annotations` и сам класс не импортирован — это приведёт к ошибке при проверке аннотаций при импорте.
- **Startup/Teardown fragility**: В `src/main.py` части старта компонентов выполняются последовательно без атомарного rollback — если `consumer.start()` упадёт, `producer` останется запущен.
- **Hardcoded/weak defaults for secrets**: В `src/core/config.py` есть значения по умолчанию для `minio_access_key` / `minio_secret_key`. В production это небезопасно.
- **No tests / CI**: Нет unit/integration тестов для критичных частей (`PDFProcessor`, `MarkdownTreeBuilder`, `MinioStorage`, Kafka adapters).
- **Unpinned dependencies**: `requirements.txt` использует ranges; для reproducible builds лучше фиксировать версии и добавлять hashes/constraints.
- **Dockerfile improvements**: образ использует `python:3.11-slim` и ставит системные пакеты, но можно уменьшить размер и улучшить caching (multi-stage, minimal apt packages, explicit non-root user).
- **Error handling and observability**: некоторые ошибки логируются и пробрасываются, но отсутствуют метрики / healthcheck / readiness endpoints и детальные структурированные ошибки.

**Improvements & Recommendations**:
- **Quick code fixes**:
  - **Service annotations**: Добавить `from __future__ import annotations` в `src/application/service.py` или импортировать `MarkdownTreeBuilder` для корректных аннотаций.
  - **Safe startup/teardown**: Обернуть запуск компонентов в blok try/except и в случае ошибки корректно остановить уже запущенные (`producer.stop()`, `consumer.stop()`, т.п.).
  - **Secrets**: Убрать чувствительные значения по умолчанию, сделать обязательными через env (например, без default для `minio_secret_key`) и документировать.

- **Testing & CI**:
  - Добавить `pytest` тесты: unit для `PDFProcessor._clean_page`, поведенческие тесты для `MarkdownTreeBuilder.build_tree`, и интеграционные для `MinioStorage` (localstack/minio тест instance).
  - Настроить CI (GitHub Actions / GitLab CI): запуск `pytest`, `mypy`/`pyright`, `flake8`/`ruff`, тест-coverage.

- **Packaging & reproducibility**:
  - Зафиксировать зависимости в `requirements.txt` (точные версии + opcional pip-compile / constraints.txt) и добавить `pip check` в CI.
  - Добавить minimal `README.md` с примерами запуска и env-переменными.

- **Docker & runtime**:
  - Использовать multi-stage build при необходимости, добавить non-root user, уменьшить слои и кеширование pip install (COPY requirements.txt -> pip install -> COPY rest).
  - Добавить liveness/readiness checks и HEALTHCHECK в Dockerfile / контейнерной конфигурации.

- **Reliability & Observability**:
  - Добавить метрики (prometheus client) и endpoint `/metrics` или интеграцию с existing monitoring.
  - Улучшить логирование ошибок (включая correlation id / trace id) и добавить structured error messages.

- **Async correctness**:
  - Проверить использование `asyncio.to_thread` (правильно для синхронных SDK), но убедиться, что исключения корректно пробрасываются и логируются.
  - Рассмотреть batching/параллелизм при обработке больших PDF (если нужно повышать throughput).

**Quick PR-level fixes (small, high-value)**:
- Add `from __future__ import annotations` to `src/application/service.py` and import `MarkdownTreeBuilder` or change annotation to `Any`.
- Wrap component startup in `try` and stop started components on failure in `src/main.py`.
- Make `minio_secret_key` required (remove default) and document env vars in README.
- Add simple unit tests for `_clean_page` and `MarkdownTreeBuilder.build_tree`.
- Pin dependencies in `requirements.txt` (at least for CI reproducibility).

**Files reviewed**:
- [src/main.py](src/main.py)
- [src/application/service.py](src/docparser/application/service.py)
- [src/core/config.py](src/docparser/core/config.py)
- [src/core/logger.py](src/docparser/core/logger.py)
- [src/domain/models.py](src/docparser/domain/models.py)
- [src/infrastructure/pdf/processor.py](src/docparser/infrastructure/pdf/processor.py)
- [src/infrastructure/pdf/tree_builder.py](src/docparser/infrastructure/pdf/tree_builder.py)
- [src/infrastructure/minio/storage.py](src/docparser/infrastructure/minio/storage.py)
- [src/infrastructure/kafka/consumer.py](src/docparser/infrastructure/kafka/consumer.py)
- [src/infrastructure/kafka/producer.py](src/docparser/infrastructure/kafka/producer.py)
- [Dockerfile](Dockerfile)
- [requirements.txt](requirements.txt)

**Next steps (suggested)**:
- Принять quick fixes (1–2 PR): аннотации, startup/teardown, секреты.
- Добавить тесты и запустить CI.
- По желанию: могу открыть PR с исправлениями для первых трёх quick fixes.

---
_Если хотите, могу автоматически создать PR с патчами для quick fixes — скажите, какие из них включать._

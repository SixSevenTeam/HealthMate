"""Настройка логирования через structlog."""

import json
import logging
import sys
import structlog

from rag.core.config import settings


def setup_logging() -> None:
    """Настраивает structlog для сервиса."""

    # Выбираем процессоры в зависимости от формата
    if settings.log_format == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(
                serializer=lambda obj, **kwargs: json.dumps(
                    obj,
                    ensure_ascii=False,
                    default=str,
                )
            ),
        ]
    else:
        # Console format (для разработки)
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.structlog_dev_mode else structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
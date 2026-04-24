"""Менеджер сессий диалога пользователя.

Сессия хранит текущий этап консультации, собранные симптомы
и количество заданных вопросов. Хранилище — Redis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import structlog

from rag.dialogue.stages import ConsultationStage

log = structlog.get_logger()


@dataclass
class Session:
    """Состояние одной диалоговой сессии консультации."""

    session_id: str
    user_id: str
    stage: ConsultationStage = ConsultationStage.ANAMNESIS
    questions_asked: int = 0
    collected_symptoms: list[str] = field(default_factory=list)
    clinical_summary: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)


class SessionManager:
    """Управляет сессиями диалога через Redis.

    Сессия хранится в Redis с TTL = anamnesis_timeout (по умолчанию 300 сек).
    При истечении TTL сессия сбрасывается и диалог начинается заново.
    """

    def __init__(self) -> None:
        self._redis = None  # TODO: инициализировать redis.asyncio.Redis

    async def get_or_create(
        self,
        session_id: str,
        user_id: str,
    ) -> Session:
        """Возвращает существующую сессию или создаёт новую.

        Args:
            session_id: Уникальный идентификатор сессии (из запроса Java).
            user_id: Идентификатор пользователя.

        Returns:
            Объект Session с текущим состоянием.
        """
        # TODO:
        # 1. Попытаться получить из Redis: redis.get(f"session:{session_id}")
        # 2. Если не найдено — создать новую Session
        # 3. Десериализовать JSON → Session
        log.warning("session_manager_not_implemented", session_id=session_id)
        return Session(session_id=session_id, user_id=user_id)

    async def update(self, session: Session) -> None:
        """Сохраняет обновлённое состояние сессии в Redis.

        Args:
            session: Обновлённый объект сессии.
        """
        # TODO:
        # 1. Сериализовать Session в JSON
        # 2. redis.setex(f"session:{session.session_id}", ttl, json)
        session.last_updated = datetime.utcnow()
        log.warning("session_update_not_implemented", session_id=session.session_id)

    async def delete(self, session_id: str) -> None:
        """Удаляет сессию из Redis (завершение диалога).

        Args:
            session_id: Идентификатор сессии для удаления.
        """
        # TODO: redis.delete(f"session:{session_id}")
        log.warning("session_delete_not_implemented", session_id=session_id)


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Возвращает singleton-экземпляр SessionManager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

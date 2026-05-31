"""Менеджер сессий диалога пользователя.

Сессия хранит текущий этап консультации, собранные симптомы
и количество заданных вопросов. Хранилище — Redis.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog

from rag.dialogue.stages import ConsultationStage

log = structlog.get_logger()

_SESSION_PREFIX = "session:"


@dataclass
class Session:
    """Состояние одной диалоговой сессии консультации."""

    session_id: str
    user_id: str
    stage: ConsultationStage = ConsultationStage.ANAMNESIS
    questions_asked: int = 0
    collected_symptoms: list[str] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    anamnesis_state: dict = field(default_factory=dict)
    clinical_summary: str = ""
    provisional_diagnosis: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json(self) -> str:
        """Serialize session to JSON string."""
        data = asdict(self)
        data["stage"] = self.stage.value
        data["created_at"] = self.created_at.isoformat()
        data["last_updated"] = self.last_updated.isoformat()
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> Session:
        """Deserialize session from JSON string."""
        data = json.loads(raw)
        data["stage"] = ConsultationStage(data["stage"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        return cls(**data)


class SessionManager:
    """Управляет сессиями диалога через Redis.

    Сессия хранится в Redis с TTL = anamnesis_timeout (по умолчанию 300 сек).
    При истечении TTL сессия сбрасывается и диалог начинается заново.
    """

    def __init__(self) -> None:
        from rag.core.config import settings

        self._redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._ttl = settings.anamnesis_timeout_seconds
        log.info("session_manager_initialized", redis_url=settings.redis_url, ttl=self._ttl)

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
        key = f"{_SESSION_PREFIX}{session_id}"
        raw = await self._redis.get(key)

        if raw:
            session = Session.from_json(raw)
            log.debug("session_loaded", session_id=session_id, stage=session.stage.value)
            return session

        session = Session(session_id=session_id, user_id=user_id)
        await self.update(session)
        log.info("session_created", session_id=session_id)
        return session

    async def update(self, session: Session) -> None:
        """Сохраняет обновлённое состояние сессии в Redis.

        Args:
            session: Обновлённый объект сессии.
        """
        session.last_updated = datetime.now(timezone.utc)
        key = f"{_SESSION_PREFIX}{session.session_id}"
        await self._redis.setex(key, self._ttl, session.to_json())
        log.debug("session_updated", session_id=session.session_id, stage=session.stage.value)

    async def delete(self, session_id: str) -> None:
        """Удаляет сессию из Redis (завершение диалога).

        Args:
            session_id: Идентификатор сессии для удаления.
        """
        key = f"{_SESSION_PREFIX}{session_id}"
        await self._redis.delete(key)
        log.info("session_deleted", session_id=session_id)


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Возвращает singleton-экземпляр SessionManager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

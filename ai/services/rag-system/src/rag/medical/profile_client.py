"""HTTP-клиент для получения медицинского профиля пользователя из Java-бэкенда.

Java-бэкенд хранит профиль пользователя: аллергии, хронические заболевания,
текущие препараты. RAG-система запрашивает его перед генерацией рекомендаций
для учёта персональных ограничений и противопоказаний.
"""

from __future__ import annotations

import structlog

from rag.domain.events import UserProfile

log = structlog.get_logger()


class MedicalProfileClient:
    """HTTP-клиент для обращения к Java-бэкенду за профилем пользователя.

    Endpoint: GET /api/medical-profile/{user_id}
    Использует httpx с retry через tenacity.
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        """
        Args:
            base_url: Базовый URL Java-бэкенда (напр. http://healthmate-api:8080).
            timeout: Таймаут запроса в секундах.
        """
        self._base_url = base_url
        self._timeout = timeout
        self._client = None  # TODO: httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get_profile(self, user_id: str) -> UserProfile:
        """Получает медицинский профиль пользователя.

        Args:
            user_id: UUID пользователя.

        Returns:
            Полный медицинский профиль пользователя.

        Raises:
            RuntimeError: Если профиль недоступен или не найден.
        """
        # TODO:
        # response = await self._client.get(f"/api/medical-profile/{user_id}")
        # response.raise_for_status()
        # return UserProfile.model_validate(response.json())
        log.warning("profile_client_not_implemented", user_id=user_id)
        return UserProfile()

    async def close(self) -> None:
        """Закрывает HTTP-соединение."""
        # TODO: await self._client.aclose()
        pass


_profile_client: MedicalProfileClient | None = None


def get_profile_client() -> MedicalProfileClient:
    """Возвращает singleton-экземпляр MedicalProfileClient."""
    global _profile_client
    if _profile_client is None:
        from rag.core.config import settings
        _profile_client = MedicalProfileClient(
            base_url=settings.java_backend_url if hasattr(settings, "java_backend_url") else "http://localhost:8080",
        )
    return _profile_client

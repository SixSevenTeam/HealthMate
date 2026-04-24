"""LLM-клиент для взаимодействия с DeepSeek API.

DeepSeek совместим с OpenAI API, поэтому используем openai-клиент
с кастомным base_url.
"""

from __future__ import annotations

from typing import AsyncIterator

import structlog

log = structlog.get_logger()


class LLMClient:
    """Клиент для работы с DeepSeek LLM через OpenAI-совместимый API.

    Используется в диалоговом движке для:
    - Генерации уточняющих вопросов (этап анамнеза)
    - Синтеза контекста (симптомы + профиль)
    - Генерации рекомендаций с учётом безопасности
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        """
        Args:
            api_key: API-ключ DeepSeek.
            base_url: Базовый URL API (напр. https://api.deepseek.com).
            model: Идентификатор модели (напр. deepseek-chat).
        """
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client = None  # TODO: инициализировать openai.AsyncOpenAI

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Отправляет сообщения в LLM и возвращает текстовый ответ.

        Args:
            messages: История диалога в формате [{"role": "user", "content": "..."}].
            system_prompt: Системный промпт с контекстом и ограничениями.
            temperature: Температура генерации (0.0 — детерминированно, 1.0 — случайно).
            max_tokens: Максимальное количество токенов в ответе.

        Returns:
            Текст ответа от LLM.

        Raises:
            RuntimeError: При ошибке API или таймауте.
        """
        # TODO: реализовать через openai.AsyncOpenAI с base_url и api_key
        log.warning("llm_client_not_implemented", model=self._model)
        pass

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Стриминговый чат — возвращает токены по мере генерации.

        Args:
            messages: История диалога.
            system_prompt: Системный промпт.
            temperature: Температура генерации.

        Yields:
            Фрагменты текста по мере получения от API.
        """
        # TODO: реализовать через openai.AsyncOpenAI с stream=True
        log.warning("llm_client_stream_not_implemented")
        return
        yield  # делает функцию генератором


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Возвращает singleton-экземпляр LLMClient."""
    global _llm_client
    if _llm_client is None:
        from rag.core.config import settings
        _llm_client = LLMClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.llm_model,
        )
    return _llm_client

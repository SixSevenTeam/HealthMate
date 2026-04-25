"""LLM-клиент для взаимодействия с DeepSeek API.

DeepSeek совместим с OpenAI API, поэтому используем openai-клиент
с кастомным base_url.
"""

from __future__ import annotations

from typing import AsyncIterator

import structlog
from openai import AsyncOpenAI

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
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        log.info("llm_client_initialized", model=model, base_url=base_url)

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
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            log.info(
                "llm_chat_complete",
                model=self._model,
                input_msgs=len(messages),
                output_len=len(content),
            )
            return content
        except Exception as e:
            log.error("llm_chat_failed", model=self._model, error=str(e))
            raise RuntimeError(f"LLM API error: {e}") from e

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
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            log.error("llm_stream_failed", model=self._model, error=str(e))
            raise RuntimeError(f"LLM stream error: {e}") from e


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

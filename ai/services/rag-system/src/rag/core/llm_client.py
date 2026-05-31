"""LLM-клиент для взаимодействия с DeepSeek API.

DeepSeek совместим с OpenAI API, поэтому используем openai-клиент
с кастомным base_url.
"""

from __future__ import annotations

from typing import AsyncIterator

import openai
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

        import os
        if os.environ.get("DEBUG_LLM", "").lower() == "true":
            log.info(
                "llm_chat_request_full",
                model=self._model,
                num_messages=len(full_messages),
                total_prompt_chars=sum(len(m.get("content", "")) for m in full_messages),
            )
            log.info("  System prompt:")
            for line in system_prompt.split("\n")[:20]:
                log.info(f"    {line}")
            if len(system_prompt.split("\n")) > 20:
                log.info(f"    ... ({len(system_prompt.split('/n')) - 20} more lines)")
            
            for i, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:500]
                log.info(f"  Message #{i+1} ({role}): {content}...")

        try:
            chunks: list[str] = []
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            reasoning_chunks: list[str] = []
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    chunks.append(delta.content)
                else:
                    extra = getattr(delta, "model_extra", None) or {}
                    rc = extra.get("reasoning_content") or ""
                    if rc:
                        reasoning_chunks.append(rc)

            content = "".join(chunks) or "".join(reasoning_chunks)
            log.info(
                "llm_chat_complete",
                model=self._model,
                input_msgs=len(messages),
                output_len=len(content),
            )

            if os.environ.get("DEBUG_LLM", "").lower() == "true":
                log.info(f"  LLM response: {content[:500]}...")

            if not content.strip():
                raise RuntimeError(f"LLM returned empty content after full stream (model={self._model})")

            return content
        except RuntimeError:
            raise
        except openai.RateLimitError as e:
            log.warning("llm_rate_limited", model=self._model, error=str(e))
            raise RuntimeError(f"LLM rate limited: {e}") from e
        except openai.APITimeoutError as e:
            log.error("llm_timeout", model=self._model, error=str(e))
            raise RuntimeError(f"LLM timeout: {e}") from e
        except openai.AuthenticationError as e:
            log.error("llm_auth_failed", model=self._model, base_url=self._base_url, hint="check DEEPSEEK_API_KEY")
            raise RuntimeError(f"LLM auth error: {e}") from e
        except openai.BadRequestError as e:
            prompt_chars = sum(len(m.get("content", "")) for m in full_messages)
            log.error("llm_bad_request", model=self._model, prompt_chars=prompt_chars, error=str(e))
            raise RuntimeError(f"LLM bad request: {e}") from e
        except Exception as e:
            log.error("llm_unexpected_error", model=self._model, error_type=type(e).__name__, error=str(e))
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

"""Tests for LLMClient (mocked OpenAI)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.core.llm_client import LLMClient


class TestLLMClient:

    @pytest.fixture
    def mock_openai(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def llm(self, mock_openai):
        with patch("rag.core.llm_client.AsyncOpenAI", return_value=mock_openai):
            c = LLMClient(api_key="test", base_url="http://test", model="test-model")
            c._client = mock_openai
            return c

    async def test_chat_success(self, llm, mock_openai):
        choice = MagicMock()
        choice.message.content = "Hello from LLM"
        response = MagicMock()
        response.choices = [choice]
        mock_openai.chat.completions.create = AsyncMock(return_value=response)

        result = await llm.chat(
            messages=[{"role": "user", "content": "Hi"}],
            system_prompt="You are helpful",
        )
        assert result == "Hello from LLM"
        mock_openai.chat.completions.create.assert_called_once()

    async def test_chat_prepends_system(self, llm, mock_openai):
        choice = MagicMock()
        choice.message.content = "ok"
        response = MagicMock()
        response.choices = [choice]
        mock_openai.chat.completions.create = AsyncMock(return_value=response)

        await llm.chat(
            messages=[{"role": "user", "content": "test"}],
            system_prompt="be nice",
        )
        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "be nice"

    async def test_chat_none_content(self, llm, mock_openai):
        choice = MagicMock()
        choice.message.content = None
        response = MagicMock()
        response.choices = [choice]
        mock_openai.chat.completions.create = AsyncMock(return_value=response)

        result = await llm.chat(
            messages=[{"role": "user", "content": "x"}],
            system_prompt="sys",
        )
        assert result == ""

    async def test_chat_error_raises_runtime(self, llm, mock_openai):
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=Exception("API down")
        )
        with pytest.raises(RuntimeError, match="LLM API error"):
            await llm.chat(
                messages=[{"role": "user", "content": "x"}],
                system_prompt="sys",
            )

    async def test_chat_temperature_and_tokens(self, llm, mock_openai):
        choice = MagicMock()
        choice.message.content = "ok"
        response = MagicMock()
        response.choices = [choice]
        mock_openai.chat.completions.create = AsyncMock(return_value=response)

        await llm.chat(
            messages=[],
            system_prompt="sys",
            temperature=0.3,
            max_tokens=100,
        )
        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 100

    async def test_chat_stream_yields_tokens(self, llm, mock_openai):
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " World"
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None

        async def mock_stream():
            for c in [chunk1, chunk2, chunk3]:
                yield c

        mock_openai.chat.completions.create = AsyncMock(return_value=mock_stream())

        tokens = []
        async for token in llm.chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            system_prompt="sys",
        ):
            tokens.append(token)

        assert tokens == ["Hello", " World"]

    async def test_chat_stream_error(self, llm, mock_openai):
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=Exception("stream fail")
        )
        with pytest.raises(RuntimeError, match="LLM stream error"):
            async for _ in llm.chat_stream(
                messages=[], system_prompt="sys"
            ):
                pass

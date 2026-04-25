"""Tests for medical disclaimer and prompts."""

from __future__ import annotations

from rag.medical.disclaimer import MEDICAL_DISCLAIMER, inject_disclaimer
from rag.dialogue.prompts import (
    ANAMNESIS_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    RECOMMENDATION_SYSTEM_PROMPT,
)


class TestDisclaimer:

    def test_disclaimer_not_empty(self):
        assert len(MEDICAL_DISCLAIMER) > 0

    def test_disclaimer_contains_warning(self):
        assert "Важно" in MEDICAL_DISCLAIMER

    def test_inject_disclaimer(self):
        result = inject_disclaimer("Рекомендация")
        assert result.startswith("Рекомендация")
        assert MEDICAL_DISCLAIMER in result


class TestPrompts:

    def test_anamnesis_prompt_has_placeholders(self):
        result = ANAMNESIS_SYSTEM_PROMPT.format(
            max_questions=3,
            user_profile_summary="Возраст: 30",
        )
        assert "3" in result
        assert "30" in result

    def test_synthesis_prompt_has_placeholders(self):
        result = SYNTHESIS_SYSTEM_PROMPT.format(
            collected_symptoms="головная боль",
            user_profile_summary="Пол: male",
        )
        assert "головная боль" in result

    def test_recommendation_prompt_has_placeholders(self):
        result = RECOMMENDATION_SYSTEM_PROMPT.format(
            clinical_summary="summary",
            retrieved_context="context",
            user_profile_summary="profile",
        )
        assert "summary" in result
        assert "context" in result

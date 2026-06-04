"""Helpers for LLM-driven guided anamnesis."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class GuidedAnswerOption(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=120)


class GuidedAnamnesisQuestion(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=5, max_length=240)
    answer_options: list[GuidedAnswerOption] = Field(min_length=1, max_length=5)
    allow_free_text: bool = True
    rationale: str | None = Field(default=None, max_length=240)


def _extract_json_string(response: str) -> str:
    """Извлекает валидную JSON-строку из ответа LLM, игнорируя лишний текст (мысли модели)."""
    response = response.strip()

    try:
        json.loads(response)
        return response
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
    if match:
        try:

            json.loads(match.group())
            return match.group()
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Не удалось извлечь валидный JSON из ответа LLM. Начало ответа: {response[:200]}")


def build_anamnesis_system_prompt() -> str:
    return """Ты — медицинский ассистент HealthMate на этапе сбора анамнеза.

Твоя задача: сгенерировать ОДИН следующий уточняющий вопрос для пациента.

Правила:
- Задавай только один вопрос за раз.
- Формулируй вопрос так, чтобы он был понятен обычному человеку.
- Дай 1-5 вариантов ответа, но обязательно оставь возможность свободного ответа.
- Не ставь диагноз и не назначай препараты.
- Вопрос должен учитывать уже собранные ответы, профиль пользователя, аллергии, диагнозы и текущие лекарства.
- Не повторяй уже заданные вопросы и не переспрашивай то, что пациент уже подтвердил.
- Пиши только на русском языке, включая поля value в answer_options.
- Если пациент отвечает кратко ("да", "всё", "все", "всё из этого"), это означает, что он подтверждает ВСЕ варианты из твоего предыдущего вопроса (смотри блок [Варианты: ...] в истории). Учитывай их все как подтвержденные факты и переходи к следующему логическому шагу.

ВАЖНО: ОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON. 
ЗАПРЕЩЕНО писать любой текст до или после JSON. Твой ответ должен начинаться строго с символа '{' и заканчиваться '}'. 

Формат JSON строго:
{
  "question_id": "краткий_идентификатор",
  "question": "текст вопроса",
  "answer_options": [
    {"label": "вариант для отображения", "value": "краткое значение на русском"}
  ],
  "allow_free_text": true,
  "rationale": "кратко, почему этот вопрос важен"
}
"""


def build_anamnesis_messages(
        *,
        user_profile_summary: str,
        collected_symptoms: list[str],
        conversation_history: list[Any],
        max_questions: int,
        questions_asked: int,
) -> list[dict[str, str]]:
    symptom_summary = "\n".join(
        f"- {item}" for item in collected_symptoms) if collected_symptoms else "- пока нет ответов"

    history_lines = []
    for message in conversation_history[-12:]:
        if isinstance(message, dict):
            role = message.get("role", "unknown")
            content = (message.get("content") or "").strip()
        else:
            role = getattr(message, "role", "unknown")
            content = (getattr(message, "content", "") or "").strip()

        if content:
            role_label = "🩺 Ассистент" if role == "assistant" else "👤 Пациент"
            history_lines.append(f"{role_label}: {content}")

    user_context = (
            f"=== ПРОФИЛЬ ПАЦИЕНТА ===\n{user_profile_summary}\n\n"
            f"=== СОБРАННЫЕ СИМПТОМЫ ===\n{symptom_summary}\n\n"
            f"=== ИСТОРИЯ ДИАЛОГА ===\n" + (
                "\n".join(history_lines) if history_lines else "- диалог только начался -") + "\n\n"
                                                                                              f"=== ИНФОРМАЦИЯ О ЭТАПЕ ===\n"
                                                                                              f"Задано вопросов: {questions_asked} из {max_questions}.\n\n"
                                                                                              f"=== ПРАВИЛА ОБРАБОТКИ ОТВЕТОВ ===\n"
                                                                                              f"Если пациент отвечает кратко ('да', 'всё', 'все', 'всё из этого', 'верно', 'нет'), "
                                                                                              f"это означает, что он ПОДТВЕРЖДАЕТ или ОТРИЦАЕТ варианты из твоего предыдущего вопроса. "
                                                                                              f"Смотри на варианты в квадратных скобках [Варианты: ...] в сообщении ассистента перед ответом пациента. "
                                                                                              f"Считай все подтверждённые варианты реальными симптомами/фактами и НЕ переспрашивай о них. "
                                                                                              f"Переходи к следующему логическому шагу: уточнение длительности, интенсивности, "
                                                                                              f"сопутствующих симптомов или триггеров."
    )

    return [{"role": "user", "content": user_context}]


def parse_guided_question(raw_text: str) -> GuidedAnamnesisQuestion:
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("LLM returned empty response — check model name and API key")


    clean_json_str = _extract_json_string(raw_text)

    data = json.loads(clean_json_str)
    return GuidedAnamnesisQuestion.model_validate(data)


def format_question_for_response(question: GuidedAnamnesisQuestion) -> dict[str, Any]:
    return {
        "questionId": question.question_id,
        "question": question.question,
        "answerOptions": [option.model_dump() for option in question.answer_options],
        "allowFreeText": question.allow_free_text,
        "inputMode": "guided",
        "rationale": question.rationale,
    }

"""Helpers for LLM-driven guided anamnesis.

The model generates exactly one next question at a time in JSON form:
- question text
- answer options
- free-text allowance
- short rationale for internal use

This keeps the interview dynamic while still allowing the frontend to render
an explicit guided UX.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class GuidedAnswerOption(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=120)


class GuidedAnamnesisQuestion(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=5, max_length=240)
    answer_options: list[GuidedAnswerOption] = Field(min_length=2, max_length=5)
    allow_free_text: bool = True
    rationale: str | None = Field(default=None, max_length=240)


def build_anamnesis_system_prompt() -> str:
    return """Ты — медицинский ассистент HealthMate на этапе сбора анамнеза.

Твоя задача: сгенерировать ОДИН следующий уточняющий вопрос для пользователя.

Правила:
- Задавай только один вопрос за раз.
- Формулируй вопрос так, чтобы он был понятен обычному человеку.
- Дай 2-5 вариантов ответа, но обязательно оставь возможность свободного ответа.
- Не ставь диагноз и не назначай препараты.
- Вопрос должен учитывать уже собранные ответы, профиль пользователя, аллергии, диагнозы и текущие лекарства.
- Не повторяй уже заданные вопросы.
- Пиши только на русском языке.
- Отвечай строго JSON-объектом без markdown, без поясняющего текста и без тройных кавычек.

Формат JSON:
{
  "question_id": "short_identifier",
  "question": "текст вопроса",
  "answer_options": [
    {"label": "вариант", "value": "значение"}
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
    symptom_summary = "\n".join(f"- {item}" for item in collected_symptoms) if collected_symptoms else "- пока нет ответов"
    history_lines = []
    for message in conversation_history[-12:]:
        if isinstance(message, dict):
            role = message.get("role", "unknown")
            content = (message.get("content") or "").strip()
        else:
            role = getattr(message, "role", "unknown")
            content = (getattr(message, "content", "") or "").strip()

        role = str(role)
        if content:
            history_lines.append(f"{role}: {content}")

    user_context = (
        f"Профиль пользователя:\n{user_profile_summary}\n\n"
        f"Уже собранные симптомы:\n{symptom_summary}\n\n"
        f"История диалога:\n" + ("\n".join(history_lines) if history_lines else "- пусто") + "\n\n"
        f"Уже задано вопросов: {questions_asked} из {max_questions}."
    )

    return [{"role": "user", "content": user_context}]


def parse_guided_question(raw_text: str) -> GuidedAnamnesisQuestion:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`\n ")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    data = json.loads(raw_text)
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

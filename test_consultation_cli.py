#!/usr/bin/env python3
"""Интерактивный CLI-тестер полного пайплайна консультации.

Отправляет запросы в endpoint /ai/chat в реальном контракте:
conversationId, userMessage, userContext, conversationHistory.

Показывает:
- полный request payload
- полный raw response
- answerOptions / question / recommendedDrugs
- текст рекомендации и выбранные препараты
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from pathlib import Path

import httpx

API_BASE_URL = "http://127.0.0.1:8001"
SESSION_ID = "test-cli-session-001"
USER_ID = "test-user-001"


def load_internal_api_key() -> str:
    """Load PYTHON_INTERNAL_API_KEY from environment or the repo root .env file."""
    env_key = os.getenv("PYTHON_INTERNAL_API_KEY", "").strip()
    if env_key:
        return env_key

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return ""

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("PYTHON_INTERNAL_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


INTERNAL_API_KEY = load_internal_api_key()

USER_CONTEXT = {
    "userId": USER_ID,
    "birthDate": None,
    "heightCm": 178,
    "weightKg": 82,
    "bloodType": "O+",
    "diagnoses": [{"name": "Гипертония", "diagnosedAt": None}],
    "allergies": [{"allergen": "пенициллин", "reaction": "сыпь"}],
    "contextDegraded": False,
    "contextWarnings": [],
    "activeMedications": [
        {
            "tradeName": "Конкор",
            "internationalName": "bisoprolol",
            "doseAmount": 5,
            "doseUnit": "mg",
            "instructions": "1 раз в день",
        }
    ],
}


def print_header(text: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text: str) -> None:
    print(f"\n▶ {text}")
    print("-" * 80)


def print_info(text: str) -> None:
    print(f"ℹ️  {text}")


def print_success(text: str) -> None:
    print(f"\n✅ {text}")


def print_error(text: str) -> None:
    print(f"\n❌ {text}")


def print_log_event(event_name: str, data: dict[str, Any]) -> None:
    print(f"\n📋 {event_name}:")
    for key, value in data.items():
        if isinstance(value, str) and len(value) > 250:
            print(f"   {key}: {value[:250]}...")
        elif isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False, indent=4)
            print(f"   {key}:")
            for line in rendered.splitlines():
                print(f"      {line}")
        else:
            print(f"   {key}: {value}")


class ConsultationTester:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.conversation_id = SESSION_ID
        self.user_id = USER_ID
        self.conversation_history: list[dict[str, str]] = []
        self.collected_symptoms: list[str] = []

    async def send_message(self, user_message: str) -> dict[str, Any]:
        payload = {
            "conversationId": self.conversation_id,
            "userMessage": user_message,
            "userContext": USER_CONTEXT,
            "conversationHistory": self.conversation_history,
            "anamnesisState": None,
        }

        print_log_event(
            "REQUEST_PAYLOAD",
            {
                "endpoint": "/ai/chat",
                "conversationId": self.conversation_id,
                "userMessage": user_message,
                "conversation_history_count": len(self.conversation_history),
                "userContext": USER_CONTEXT,
                "internal_api_key_loaded": bool(INTERNAL_API_KEY),
            },
        )

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                headers = {"Content-Type": "application/json"}
                if INTERNAL_API_KEY:
                    headers["X-Internal-Key"] = INTERNAL_API_KEY
                response = await client.post(
                    f"{self.base_url}/ai/chat",
                    json=payload,
                    headers=headers,
                )
        except Exception as exc:
            print_error(f"Ошибка HTTP: {exc}")
            return {}

        print_info(f"Статус API: {response.status_code}")
        if response.status_code != 200:
            print_error("API вернул не-200 ответ")
            print(response.text)
            return {}

        try:
            data = response.json()
        except Exception as exc:
            print_error(f"Не удалось распарсить JSON ответа: {exc}")
            print(response.text)
            return {}

        print_log_event("RAW_RESPONSE", data)
        return data

    async def run(self) -> None:
        print_header("ТЕСТЕР КОНСУЛЬТАЦИИ HEALTHMATE")
        print_info("Это интерактивная консольная проверка полного пайплайна.")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health = await client.get(f"{self.base_url}/docs")
                if health.status_code == 200:
                    print_success(f"API доступен: {self.base_url}")
                else:
                    print_error(f"API отвечает статусом {health.status_code}")
                    return
        except Exception as exc:
            print_error(f"Не удалось подключиться к API: {exc}")
            print_info("Сначала запусти сервер:")
            print_info("cd ai/services/rag-system")
            print_info("python -m uvicorn rag.app:app --reload --host 0.0.0.0 --port 8001")
            return

        print_section("Профиль пациента")
        print_log_event("USER_CONTEXT", USER_CONTEXT)

        user_message = input("\n📝 Введите первую жалобу: ").strip()
        if not user_message:
            print_error("Пустая жалоба")
            return

        while True:
            response = await self.send_message(user_message)
            if not response:
                return

            message_type = response.get("messageType", "")
            content = response.get("content", "")
            question = response.get("question") or ""
            answer_options = response.get("answerOptions", [])
            anamnesis_state = response.get("anamnesisState") or {}
            recommended_drugs = response.get("recommendedDrugs") or []

            print_log_event(
                "RESPONSE_META",
                {
                    "messageType": message_type,
                    "question": question,
                    "answerOptions": answer_options,
                    "anamnesisState": anamnesis_state,
                    "recommendedDrugsCount": len(recommended_drugs),
                },
            )

            self.conversation_history.append({"role": "user", "content": user_message})

            if message_type == "question" and question:
                print_section("Вопрос от системы")
                print(question)
                if answer_options:
                    print_info(f"Варианты ответа: {json.dumps(answer_options, ensure_ascii=False)}")

                user_message = input("\n📝 Ваш ответ: ").strip()
                if not user_message:
                    print_error("Пустой ответ")
                    return

                self.conversation_history.append({"role": "assistant", "content": question})
                self.collected_symptoms.append(user_message)
                continue

            print_section("ОТВЕТ СИСТЕМЫ")
            if content:
                print(content)

            if recommended_drugs:
                print_section("РЕКОМЕНДУЕМЫЕ ПРЕПАРАТЫ")
                for index, drug in enumerate(recommended_drugs, 1):
                    print(f"\n{index}. {drug.get('name', 'Unknown')}")
                    if drug.get("reason"):
                        print(f"   Почему: {drug['reason']}")
                    if drug.get("dosage"):
                        print(f"   Дозировка: {drug['dosage']}")
                    if drug.get("contraindications"):
                        print(f"   Противопоказания: {drug['contraindications']}")
                    if drug.get("drugId"):
                        print(f"   drugId: {drug['drugId']}")

            print_success("Консультация завершена")
            return


async def main() -> None:
    tester = ConsultationTester(API_BASE_URL)
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())

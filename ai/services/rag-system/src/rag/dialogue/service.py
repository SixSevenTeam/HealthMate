"""Диалоговый сервис медицинской консультации.

Оркестрирует трёхэтапный диалог:
1. Сбор анамнеза — уточняющие вопросы о симптомах.
2. Синтез контекста — наложение симптомов на профиль пользователя.
3. Генерация рекомендаций — безопасные советы с учётом профиля.
"""

from __future__ import annotations

import time
import uuid

import structlog

from rag.core.config import settings
from rag.core.llm_client import get_llm_client
from rag.dialogue.prompts import (
    ANAMNESIS_SYSTEM_PROMPT,
    MEDICAL_DISCLAIMER,
    RECOMMENDATION_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from rag.dialogue.session import Session, SessionManager, get_session_manager
from rag.dialogue.stages import ConsultationStage
from rag.domain.events import (
    ContextUsed,
    QueryRequest,
    QueryResponse,
    ResponseMetadata,
    RetrievedDocument,
)

log = structlog.get_logger()


class DialogueService:
    """Главный оркестратор медицинской консультации.

    Получает запрос от Java-бэкенда (QueryRequest), определяет текущий
    этап диалога по состоянию сессии и вызывает соответствующий обработчик.
    Каждый ответ содержит медицинский дисклеймер.
    """

    def __init__(self, session_manager: SessionManager | None = None) -> None:
        self._sessions = session_manager or get_session_manager()

    async def process_query(self, request: QueryRequest) -> QueryResponse:
        """Обрабатывает запрос пользователя и возвращает ответ нужного этапа.

        Args:
            request: Полный запрос с историей диалога и профилем пользователя.

        Returns:
            Ответ, соответствующий текущему этапу консультации.
        """
        log.debug(
            "dialogue_process_query",
            user_id=request.user_id,
            session_id=request.session_id,
        )

        session = await self._sessions.get_or_create(
            request.session_id, request.user_id
        )
        stage = await self._determine_stage(session, request)

        if stage == ConsultationStage.ANAMNESIS:
            return await self._collect_anamnesis(request, session)
        elif stage == ConsultationStage.SYNTHESIS:
            return await self._synthesize_context(request, session)
        else:
            return await self._generate_recommendation(request, session)

    async def _determine_stage(
        self,
        session: Session,
        request: QueryRequest,
    ) -> ConsultationStage:
        """Определяет текущий этап консультации по состоянию сессии.

        Переход к следующему этапу происходит когда:
        - ANAMNESIS → SYNTHESIS: задано max_clarifying_questions вопросов.
        - SYNTHESIS → RECOMMENDATION: синтез выполнен (clinical_summary заполнен).

        Args:
            session: Текущее состояние сессии.
            request: Входящий запрос.
        """
        if session.stage == ConsultationStage.RECOMMENDATION:
            return ConsultationStage.RECOMMENDATION

        if session.stage == ConsultationStage.SYNTHESIS or (
            session.questions_asked >= settings.max_clarifying_questions
            and not session.clinical_summary
        ):
            return ConsultationStage.SYNTHESIS

        if session.clinical_summary:
            return ConsultationStage.RECOMMENDATION

        return ConsultationStage.ANAMNESIS

    async def _collect_anamnesis(
        self,
        request: QueryRequest,
        session: Session,
    ) -> QueryResponse:
        """Этап 1: Генерирует уточняющий вопрос об анамнезе.

        Использует LLM с промптом ANAMNESIS_SYSTEM_PROMPT.
        Сохраняет симптомы из ответов пользователя в сессию.

        Args:
            request: Входящий запрос.
            session: Текущая сессия.
        """
        start = time.monotonic()
        llm = get_llm_client()

        profile_summary = self._format_profile(request)
        system_prompt = ANAMNESIS_SYSTEM_PROMPT.format(
            max_questions=settings.max_clarifying_questions,
            user_profile_summary=profile_summary,
        )

        messages = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]
        messages.append({"role": "user", "content": request.query})

        response_text = await llm.chat(messages, system_prompt, temperature=0.6)

        session.questions_asked += 1
        session.messages = messages + [{"role": "assistant", "content": response_text}]
        session.stage = ConsultationStage.ANAMNESIS
        await self._sessions.update(session)

        elapsed = int((time.monotonic() - start) * 1000)
        log.info("anamnesis_step", session_id=session.session_id, q=session.questions_asked)

        return QueryResponse(
            request_id=str(uuid.uuid4()),
            session_id=session.session_id,
            stage="anamnesis_collection",
            response_type="clarifying_question",
            content={"message": response_text, "disclaimer": MEDICAL_DISCLAIMER},
            next_action="await_user_response",
            metadata=ResponseMetadata(
                processing_time_ms=elapsed,
                llm_model=settings.llm_model,
                questions_asked=session.questions_asked,
                max_questions=settings.max_clarifying_questions,
            ),
        )

    async def _synthesize_context(
        self,
        request: QueryRequest,
        session: Session,
    ) -> QueryResponse:
        """Этап 2: Синтезирует клиническую картину из симптомов и профиля.

        Запрашивает у Java-бэкенда актуальный профиль пользователя,
        совмещает с собранными симптомами и получает clinical_summary от LLM.

        Args:
            request: Входящий запрос.
            session: Текущая сессия.
        """
        start = time.monotonic()
        llm = get_llm_client()

        profile_summary = self._format_profile(request)
        symptoms_text = "\n".join(
            f"- {s}" for s in session.collected_symptoms
        ) if session.collected_symptoms else "(из диалога)"

        system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(
            collected_symptoms=symptoms_text,
            user_profile_summary=profile_summary,
        )

        messages = session.messages or [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]

        clinical_summary = await llm.chat(
            messages, system_prompt, temperature=0.4, max_tokens=1024,
        )

        session.clinical_summary = clinical_summary
        session.stage = ConsultationStage.RECOMMENDATION
        await self._sessions.update(session)

        elapsed = int((time.monotonic() - start) * 1000)
        log.info("synthesis_complete", session_id=session.session_id)

        return QueryResponse(
            request_id=str(uuid.uuid4()),
            session_id=session.session_id,
            stage="context_synthesis",
            response_type="synthesis_result",
            content={
                "message": "Анализирую информацию и подбираю рекомендации...",
                "clinical_summary": clinical_summary,
                "disclaimer": MEDICAL_DISCLAIMER,
            },
            next_action="generate_recommendation",
            metadata=ResponseMetadata(
                processing_time_ms=elapsed,
                llm_model=settings.llm_model,
                questions_asked=session.questions_asked,
            ),
        )

    async def _generate_recommendation(
        self,
        request: QueryRequest,
        session: Session,
    ) -> QueryResponse:
        """Этап 3: Генерирует финальные рекомендации.

        Выполняет RAG-поиск по clinical_summary, проверяет безопасность
        рекомендаций через SafetyChecker, формирует ответ через LLM.
        К каждому ответу добавляется медицинский дисклеймер.

        Args:
            request: Входящий запрос.
            session: Текущая сессия с clinical_summary.
        """
        start = time.monotonic()
        llm = get_llm_client()

        from rag.retrieval.retriever import get_retriever
        retriever = get_retriever()
        chunks = await retriever.retrieve(
            session.clinical_summary or request.query,
            top_k=settings.retrieval_top_k,
        )

        retrieved_context = "\n\n---\n\n".join(
            f"[{c.metadata.get('section_path', [])}]\n{c.text}"
            for c in chunks
        ) if chunks else "(медицинские материалы не найдены)"

        profile_summary = self._format_profile(request)

        system_prompt = RECOMMENDATION_SYSTEM_PROMPT.format(
            clinical_summary=session.clinical_summary or "не определена",
            retrieved_context=retrieved_context,
            user_profile_summary=profile_summary,
        )

        messages = session.messages or [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]

        response_text = await llm.chat(
            messages, system_prompt, temperature=0.5, max_tokens=2048,
        )

        from rag.medical.safety_checker import SafetyChecker
        safety = SafetyChecker()
        safety_warnings = safety.check_allergies(
            response_text,
            request.user_profile.allergies,
        )

        final_text = response_text + MEDICAL_DISCLAIMER

        await self._sessions.delete(session.session_id)

        elapsed = int((time.monotonic() - start) * 1000)
        log.info("recommendation_generated", session_id=session.session_id)

        return QueryResponse(
            request_id=str(uuid.uuid4()),
            session_id=session.session_id,
            stage="recommendation",
            response_type="medical_recommendation",
            content={
                "message": final_text,
                "disclaimer": MEDICAL_DISCLAIMER,
            },
            context_used=ContextUsed(
                retrieved_documents=[
                    RetrievedDocument(
                        document_id=c.document_id,
                        chunk_id=c.chunk_id,
                        relevance_score=c.score,
                        snippet=c.text[:200],
                    )
                    for c in chunks
                ],
                user_constraints_applied=[
                    f"allergy:{a}" for a in request.user_profile.allergies
                ],
                safety_checks_performed=safety_warnings or ["no_issues_found"],
            ),
            next_action="session_complete",
            metadata=ResponseMetadata(
                processing_time_ms=elapsed,
                llm_model=settings.llm_model,
                questions_asked=session.questions_asked,
            ),
        )

    @staticmethod
    def _format_profile(request: QueryRequest) -> str:
        """Formats user profile into a summary string for LLM prompts."""
        p = request.user_profile
        parts = []
        if p.age:
            parts.append(f"Возраст: {p.age}")
        if p.gender:
            parts.append(f"Пол: {p.gender}")
        if p.allergies:
            parts.append(f"Аллергии: {', '.join(p.allergies)}")
        if p.chronic_conditions:
            conds = [c.name for c in p.chronic_conditions]
            parts.append(f"Хронические заболевания: {', '.join(conds)}")
        if p.current_medications:
            meds = [f"{m.name} ({m.dosage})" for m in p.current_medications]
            parts.append(f"Текущие препараты: {', '.join(meds)}")
        return "\n".join(parts) if parts else "Профиль не указан"


_dialogue_service: DialogueService | None = None


def get_dialogue_service() -> DialogueService:
    """Возвращает singleton-экземпляр DialogueService."""
    global _dialogue_service
    if _dialogue_service is None:
        _dialogue_service = DialogueService()
    return _dialogue_service

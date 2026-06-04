"""Диалоговый сервис медицинской консультации.

Оркестрирует трёхэтапный диалог:
1. Сбор анамнеза — уточняющие вопросы о симптомах.
2. Синтез контекста — наложение симптомов на профиль пользователя.
3. Генерация рекомендаций — безопасные советы с учётом профиля.
"""

from __future__ import annotations

import time
import uuid
import json

import structlog
from typing import Any

from rag.core.config import settings
from rag.core.llm_client import get_llm_client
from rag.dialogue.anamnesis import (
    build_anamnesis_messages,
    build_anamnesis_system_prompt,
    format_question_for_response,
    parse_guided_question,
)
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
        """Этап 1: Генерирует guided-вопрос по анамнезу через LLM.

        Модель возвращает JSON с одним вопросом, вариантами ответа и возможностью
        свободного ввода. Это позволяет вести диалог по одному шагу, но без
        статического банка вопросов.

        Args:
            request: Входящий запрос.
            session: Текущая сессия.
        """
        start = time.monotonic()
        profile_summary = self._format_profile(request)

        user_text = request.query.strip()
        if user_text:
            session.collected_symptoms.append(user_text)

        guided_question_model = None
        if not settings.deepseek_api_key.strip():
            raise RuntimeError(
                "DeepSeek API key not configured. Anamnesis requires LLM. "
                "Set DEEPSEEK_API_KEY environment variable."
            )
        
        llm = get_llm_client()
        anamnesis_messages = build_anamnesis_messages(
            user_profile_summary=profile_summary,
            collected_symptoms=session.collected_symptoms,
            conversation_history=request.conversation_history,
            max_questions=settings.max_clarifying_questions,
            questions_asked=session.questions_asked,
        )

        system_prompt = build_anamnesis_system_prompt()

        try:
            raw_question = await llm.chat(
                anamnesis_messages,
                system_prompt,
                temperature=0.3,
                max_tokens=1500,
            )


            guided_question_model = parse_guided_question(raw_question)

            log.info(
                "anamnesis_question_generated",
                question_id=guided_question_model.question_id,
                question=guided_question_model.question[:100],
                options_count=len(guided_question_model.answer_options),
                session_id=session.session_id,
            )

        except Exception as exc:
            log.error(
                "anamnesis_llm_generation_failed",
                error=str(exc),
                session_id=session.session_id,
                raw_response_sample=(raw_question[:200] if 'raw_question' in locals() else "unknown")
            )

            log.warning(
                "anamnesis_fallback_triggered",
                reason=str(exc),
                symptoms_count=len(session.collected_symptoms),
                questions_asked=session.questions_asked,
                session_id=session.session_id,
            )


            from rag.dialogue.anamnesis import GuidedAnamnesisQuestion, GuidedAnswerOption

            guided_question_model = GuidedAnamnesisQuestion(
                question_id="fallback_general",
                question="Расскажите, пожалуйста, подробнее о ваших симптомах: как давно они начались и есть ли другие жалобы, которые вас беспокоят?",
                answer_options=[
                    GuidedAnswerOption(label="Хочу описать своими словами", value="другое")
                ],
                allow_free_text=True,
                rationale="LLM failed to generate valid JSON, using safe fallback."
            )

        guided_question = format_question_for_response(guided_question_model)

        session.questions_asked += 1
        session.anamnesis_state = {
            "stage": "collecting",
            "questionId": guided_question_model.question_id,
            "questionsAsked": session.questions_asked,
            "maxQuestions": settings.max_clarifying_questions,
            "currentQuestion": guided_question,
            "collectedSymptoms": list(session.collected_symptoms[-10:]),
        }

        session.messages = []

        for m in request.conversation_history:
            session.messages.append({"role": m.role, "content": m.content})


        assistant_content = guided_question_model.question
        if guided_question_model.answer_options:
            options_list = [opt.label for opt in guided_question_model.answer_options]
            assistant_content += f"\n[Варианты: {', '.join(options_list)}]"

        session.messages.append({"role": "assistant", "content": assistant_content})

        session.stage = ConsultationStage.ANAMNESIS
        await self._sessions.update(session)
        session.stage = ConsultationStage.ANAMNESIS
        await self._sessions.update(session)

        elapsed = int((time.monotonic() - start) * 1000)
        log.info(
            "anamnesis_step",
            session_id=session.session_id,
            q=session.questions_asked,
            question_id=guided_question_model.question_id,
        )

        return QueryResponse(
            request_id=str(uuid.uuid4()),
            session_id=session.session_id,
            stage="anamnesis_collection",
            response_type="clarifying_question",
            content={
                "message": guided_question_model.question,
                "question": guided_question_model.question,
                "answer_options": guided_question["answerOptions"],
                "allow_free_text": guided_question["allowFreeText"],
                "input_mode": guided_question["inputMode"],
                "anamnesis_state": session.anamnesis_state,
                "profile_summary": profile_summary,
                "disclaimer": MEDICAL_DISCLAIMER,
            },
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

        parsed_summary: dict[str, Any] = {}
        try:
            parsed_summary = json.loads(clinical_summary)
        except json.JSONDecodeError:
            parsed_summary = {}

        session.clinical_summary = str(
            parsed_summary.get("clinical_summary") or clinical_summary
        )
        session.provisional_diagnosis = str(
            parsed_summary.get("provisional_diagnosis") or ""
        )
        session.stage = ConsultationStage.RECOMMENDATION
        await self._sessions.update(session)

        log.info(
            "synthesis_complete",
            session_id=session.session_id,
            provisional_diagnosis=session.provisional_diagnosis,
            clinical_summary_len=len(session.clinical_summary),
        )

        return await self._generate_recommendation(request, session)

    async def _generate_recommendation(
            self,
            request: QueryRequest,
            session: Session,
    ) -> QueryResponse:
        """Этап 3: Генерирует финальные рекомендации.

        Выполняет RAG-поиск по clinical_summary, проверяет безопасность
        рекомендаций через SafetyChecker, формирует ответ через LLM.
        К каждому ответу добавляется медицинский дисклеймер.

        Ключевые оптимизации:
        - Умное ограничение контекста до 180K символов (~60K токенов)
        - НЕ передаём историю диалога (она уже в clinical_summary)
        - Retry при невалидном JSON от LLM
        - Пониженная температура (0.3) для стабильности

        Args:
            request: Входящий запрос.
            session: Текущая сессия с clinical_summary.
        """
        start = time.monotonic()
        llm = get_llm_client()

        log.info("recommendation_generation_started", session_id=session.session_id)

        from rag.retrieval.retriever import get_retriever
        retriever = get_retriever()


        query_for_retrieval = "\n".join(
            part
            for part in [
                session.provisional_diagnosis.strip(),
                session.clinical_summary.strip(),
                request.query.strip(),
            ]
            if part
        ) or request.query
        log.info(
            "retrieval_query",
            query_text=query_for_retrieval[:100],
            session_id=session.session_id,
        )

        chunks = await retriever.retrieve(
            query_for_retrieval,
            top_k=settings.retrieval_top_k,
        )
        log.info("retrieval_result", chunk_count=len(chunks), session_id=session.session_id)

        unique_doc_count = len({c.document_id for c in chunks})


        import os
        if os.environ.get("DEBUG_RETRIEVAL", "").lower() == "true":
            log.info(f"  📋 Retrieved {len(chunks)} chunks for LLM:")
            for i, chunk in enumerate(chunks, 1):
                log.info(
                    f"    Chunk #{i}",
                    score=chunk.score,
                    document_id=chunk.document_id,
                    section_path=chunk.metadata.get("section_path"),
                    drug_id=chunk.metadata.get("drug_id"),
                )
                log.info(f"      Full text: {chunk.text[:500]}...")
                log.info(f"      Full metadata: {chunk.metadata}")


        unique_drug_ids = list(set(
            c.metadata.get("drug_id")
            for c in chunks
            if c.metadata.get("drug_id")
        ))
        log.info(
            "extracted_drug_ids",
            count=len(unique_drug_ids),
            drug_ids=unique_drug_ids[:10],
            session_id=session.session_id,
        )


        from rag.medical.drugs_client import get_drugs_by_ids

        full_drugs_data = await get_drugs_by_ids(unique_drug_ids)
        log.info(
            "fetched_full_drugs_from_java",
            total_requested=len(unique_drug_ids),
            successfully_fetched=sum(1 for v in full_drugs_data.values() if v),
            session_id=session.session_id,
        )


        log.info(
            "full_drugs_data_keys_and_tradenames",
            session_id=session.session_id,
            total_count=len(full_drugs_data),
            drug_ids=[str(k) for k in list(full_drugs_data.keys())[:10]],
            tradenames=[
                drug_data.get("tradeName") if drug_data else None
                for drug_data in list(full_drugs_data.values())[:10]
            ]
        )

        if os.environ.get("DEBUG_RETRIEVAL", "").lower() == "true":
            log.info(f"  📦 Full drug data from Java backend ({len(full_drugs_data)} drugs):")
            for drug_id, drug_data in list(full_drugs_data.items())[:5]:
                if drug_data:
                    log.info(
                        f"    Drug {drug_id}",
                        name=drug_data.get("tradeName") or drug_data.get("name"),
                        indication_len=len(drug_data.get("indications") or ""),
                        contraindications_len=len(drug_data.get("contraindications") or ""),
                    )
                    log.info(f"      Full data: {str(drug_data)[:1000]}...")
                else:
                    log.info(f"    Drug {drug_id}: FAILED TO FETCH")
            if len(full_drugs_data) > 5:
                log.info(f"    ... and {len(full_drugs_data) - 5} more drugs")


        MAX_CONTEXT_CHARS = 180_000

        retrieved_context_parts = []
        included_ids: list[str] = []
        current_context_size = 0
        skipped_drugs: list[str] = []

        for drug_id, drug_data in full_drugs_data.items():
            if not drug_data:
                continue


            html_content = drug_data.get("html", "")
            html_length = drug_data.get("html_length", len(html_content))


            wrapper_size = len(html_content) + 100
            if current_context_size + wrapper_size > MAX_CONTEXT_CHARS:
                log.info(
                    "context_limit_reached",
                    session_id=session.session_id,
                    drug_id=drug_id,
                    current_size=current_context_size,
                    would_add=wrapper_size,
                    limit=MAX_CONTEXT_CHARS,
                    reason="stopping_to_avoid_context_overflow",
                )
                skipped_drugs.append(drug_id)
                continue

            log.info(
                "drug_html_received",
                drug_id=drug_id,
                html_size_bytes=html_length,
                session_id=session.session_id,
            )

            if html_content:
                included_ids.append(drug_id)
                wrapper = (
                    f"=== BEGIN DRUG {drug_id} ===\n"
                    f"{html_content}\n"
                    f"=== END DRUG {drug_id} ==="
                )
                retrieved_context_parts.append(wrapper)
                current_context_size += len(wrapper)

        retrieved_context = "\n\n".join(retrieved_context_parts) if retrieved_context_parts else "(препараты не найдены в базе)"

        log.info(
            "retrieved_context_prepared",
            session_id=session.session_id,
            context_len=len(retrieved_context),
            drugs_count=len([d for d in full_drugs_data.values() if d]),
            preview=retrieved_context[:2000],
        )

        log.info(
            "retrieved_context_includes",
            session_id=session.session_id,
            included_count=len(included_ids),
            included_ids=included_ids[:20],
        )

        log.info(
            "context_final_size",
            session_id=session.session_id,
            total_chars=current_context_size,
            total_tokens_approx=current_context_size // 3,
            drugs_included=len(included_ids),
            drugs_skipped=len(skipped_drugs),
            skipped_ids=skipped_drugs[:10],
            limit=MAX_CONTEXT_CHARS,
            usage_percent=round(current_context_size / MAX_CONTEXT_CHARS * 100, 1),
        )

        if os.environ.get("DEBUG_RETRIEVAL", "").lower() == "true":
            log.info(
                "full_drugs_html_context_for_llm",
                session_id=session.session_id,
                context_len=len(retrieved_context),
                preview=retrieved_context[:2000],
            )

        profile_summary = self._format_profile(request)
        log.info("profile_formatted", session_id=session.session_id)

        log.info(
            "recommendation_input_summary",
            session_id=session.session_id,
            provisional_diagnosis=session.provisional_diagnosis,
            clinical_summary=session.clinical_summary[:500],
        )


        included_ids_set = set(included_ids)
        candidate_list_items = []
        seen_candidate_ids: set[str] = set()

        for drug_id in unique_drug_ids:
            if not drug_id or drug_id in seen_candidate_ids:
                continue

            if drug_id not in included_ids_set:
                log.debug(
                    "candidate_skipped_not_in_context",
                    drug_id=drug_id,
                    session_id=session.session_id,
                )
                continue

            seen_candidate_ids.add(drug_id)
            chunk_hint = next(
                (c for c in chunks if str(c.metadata.get("drug_id")) == str(drug_id)),
                None,
            )
            candidate_list_items.append(
                {
                    "id": str(drug_id),
                    "name": str(
                        (chunk_hint.metadata.get("trade_name") if chunk_hint else None)
                        or (chunk_hint.metadata.get("drug_name") if chunk_hint else None)
                        or (chunk_hint.metadata.get("title") if chunk_hint else None)
                        or ""
                    ),
                    "indications": str((chunk_hint.text if chunk_hint else "")[:300]),
                    "contraindications": str(
                        (chunk_hint.metadata.get("contraindications") if chunk_hint else "") or ""
                    )[:300],
                    "snippet": str((chunk_hint.text if chunk_hint else "")[:300]),
                }
            )

        log.info(
            "candidate_list_from_chunks_prepared",
            session_id=session.session_id,
            candidate_count=len(candidate_list_items),
            source_drug_ids=unique_drug_ids[:20],
            included_in_context=len(included_ids),
        )


        if candidate_list_items:
            candidate_list_text = "\n".join(
                f"id:{it['id']} | name:{it['name']} | indications:{it['indications'][:150]} | contraindications:{it['contraindications'][:150]} | snippet:{it['snippet'][:150]}"
                for it in candidate_list_items
            )
        else:
            candidate_list_text = "(no candidates)"

        log.info(
            "candidate_list_prepared",
            session_id=session.session_id,
            candidate_count=len(candidate_list_items),
            preview=candidate_list_text[:1000],
        )


        if os.environ.get("DEBUG_RETRIEVAL", "").lower() == "true":
            log.info(f"  💊 Candidate drugs for LLM ({len(candidate_list_items)} total):")
            for i, cand in enumerate(candidate_list_items[:10], 1):
                log.info(
                    f"    Drug #{i}",
                    id=cand.get("id"),
                    name=cand.get("name"),
                    indications=cand.get("indications")[:200] if cand.get("indications") else "",
                )
            if len(candidate_list_items) > 10:
                log.info(f"    ... and {len(candidate_list_items) - 10} more")


        system_prompt = RECOMMENDATION_SYSTEM_PROMPT.format(
            clinical_summary=session.clinical_summary or "не определена",
            provisional_diagnosis=session.provisional_diagnosis or "не определен",
            retrieved_context=retrieved_context,
            user_profile_summary=profile_summary,
            candidate_list=candidate_list_text,
        )
        log.info(
            "system_prompt_formatted",
            prompt_len=len(system_prompt),
            session_id=session.session_id,
        )


        if os.environ.get("DEBUG_LLM", "").lower() == "true":
            log.info(
                "llm_system_prompt_full",
                session_id=session.session_id,
                full_prompt=system_prompt,
            )

        messages = []
        log.info(
            "messages_prepared",
            msg_count=len(messages),
            session_id=session.session_id,
            note="history_omitted_for_stability",
        )

        log.info("calling_llm_for_recommendation", session_id=session.session_id)


        try:

            response_text = await llm.chat(
                messages, system_prompt, temperature=0.3, max_tokens=4000,
            )
            log.info(
                "llm_response_received",
                response_len=len(response_text),
                session_id=session.session_id,
                attempt=1,
            )

            log.info(
                "llm_response_raw_full",
                response_text=response_text,
                response_len=len(response_text),
            )


            if not response_text.strip().startswith('{'):
                log.warning(
                    "recommendation_llm_returned_text_instead_of_json",
                    session_id=session.session_id,
                    response_sample=response_text[:200],
                )


                strict_system_prompt = (
                        system_prompt +
                        "\n\n⚠️ КРИТИЧЕСКИ ВАЖНО: ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО JSON. "
                        "НАЧНИ СТРОГО С СИМВОЛА '{' И ЗАКОНЧИ '}'. "
                        "ЗАПРЕЩЕНО ПИСАТЬ ЛЮБОЙ ТЕКСТ ДО ИЛИ ПОСЛЕ JSON."
                )
                response_text = await llm.chat(
                    messages, strict_system_prompt, temperature=0.1, max_tokens=4000,
                )
                log.info(
                    "recommendation_retry_attempt",
                    session_id=session.session_id,
                    attempt=2,
                    response_len=len(response_text),
                )
                log.info(
                    "llm_response_raw_full_retry",
                    response_text=response_text,
                    response_len=len(response_text),
                )

            import json
            from rag.medical.drugs_client import (
                search_drug_by_name,
                get_drug_by_id,
            )

            recommendation_data: dict[str, Any] = {}
            parsed_successfully = False


            try:
                recommendation_data = json.loads(response_text)
                parsed_successfully = True
                log.info(
                    "recommendation_data_parsed",
                    medications_count=len(recommendation_data.get("medications", [])),
                    has_intro=bool(recommendation_data.get("intro")),
                    has_measures=bool(recommendation_data.get("nonMedicalMeasures")),
                    has_warnings=bool(recommendation_data.get("warnings")),
                    selected_ids_count=len(recommendation_data.get("selectedDrugIds", [])),
                )
                log.info(
                    "recommended_medications_from_llm",
                    session_id=session.session_id,
                    medication_names=[
                        med.get("name", "")
                        for med in recommendation_data.get("medications", [])
                        if isinstance(med, dict) and med.get("name")
                    ],
                    selected_ids=recommendation_data.get("selectedDrugIds"),
                )
            except json.JSONDecodeError as e:
                log.warning(
                    "recommendation_json_parse_error_attempt1",
                    error=str(e),
                    response_sample=response_text[:200],
                    session_id=session.session_id,
                )


            if not parsed_successfully:
                import re
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    try:
                        recommendation_data = json.loads(match.group())
                        parsed_successfully = True
                        log.info(
                            "recommendation_json_extracted_via_regex",
                            session_id=session.session_id,
                        )
                    except json.JSONDecodeError:
                        pass


            if not parsed_successfully:

                repaired = response_text.rstrip()
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')


                if repaired.count('"') % 2 != 0:
                    repaired += '"'


                repaired += ']' * open_brackets
                repaired += '}' * open_braces

                try:
                    recommendation_data = json.loads(repaired)
                    parsed_successfully = True
                    log.info(
                        "recommendation_json_repaired",
                        session_id=session.session_id,
                        original_len=len(response_text),
                        repaired_len=len(repaired),
                    )
                except json.JSONDecodeError as e:
                    log.warning(
                        "recommendation_json_repair_failed",
                        error=str(e),
                        session_id=session.session_id,
                    )


            if not parsed_successfully:
                log.warning(
                    "recommendation_json_parse_all_attempts_failed",
                    session_id=session.session_id,
                    response_sample=response_text[:300],
                )
                recommendation_data = {
                    "intro": response_text,
                    "medications": [],
                    "nonMedicalMeasures": [],
                    "warnings": [],
                    "whenToSeekHelp": "",
                }

            medications_enriched: list[dict[str, Any]] = []


            selected_ids = recommendation_data.get("selectedDrugIds") or []
            reasons_map = recommendation_data.get("reasons") or {}
            if selected_ids:
                log.info("enriching_selected_ids", count=len(selected_ids), session_id=session.session_id)
                for did in selected_ids:
                    did_str = str(did)

                    drug_info = None
                    try:
                        drug_info = full_drugs_data.get(did_str)
                    except Exception:
                        drug_info = None


                    log.info(
                        "enrichment_drug_lookup",
                        drug_id=did_str,
                        found_in_full_drugs_data=drug_info is not None,
                        trade_name_if_found=drug_info.get("tradeName") if drug_info else None,
                        session_id=session.session_id,
                    )

                    if not drug_info:
                        try:
                            drug_info = await get_drug_by_id(did_str)
                            log.info(
                                "fallback_get_drug_by_id",
                                drug_id=did_str,
                                trade_name=drug_info.get("tradeName") if drug_info else None,
                                session_id=session.session_id,
                            )
                        except Exception as exc:
                            log.debug("get_drug_by_id_failed", error=str(exc), drug_id=did_str)

                    final_name = drug_info.get("tradeName") if drug_info else did_str
                    log.info(
                        "enrichment_final_name",
                        drug_id=did_str,
                        final_name=final_name,
                        session_id=session.session_id,
                    )

                    enriched = {
                        "name": final_name,
                        "dosage": (drug_info.get("dosage") if drug_info else ""),
                        "reason": reasons_map.get(did_str) or reasons_map.get(did) or "",
                        "contraindications": (drug_info.get("contraindications") if drug_info else ""),
                        "notes": (drug_info.get("notes") if drug_info else ""),
                        "drugId": did_str,
                        "detailsUrl": f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/{did_str}/details",
                        "imageUrl": f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/{did_str}/pack-image" if (drug_info and drug_info.get("hasMedia")) else None,
                        "hasMedia": bool(drug_info and drug_info.get("hasMedia")),
                    }
                    medications_enriched.append(enriched)
            else:

                log.info(
                    "enriching_medications_started",
                    med_count=len(recommendation_data.get("medications", [])),
                )
                for med in recommendation_data.get("medications", []):
                    med_name = med.get("name", "").strip()
                    if not med_name:
                        continue

                    drug_hit = None
                    try:
                        drug_hit = await search_drug_by_name(med_name)
                    except Exception as exc:
                        log.debug(
                            "drug_search_failed_in_recommendation",
                            error=str(exc),
                            name=med_name,
                        )

                    enriched = {
                        "name": med_name,
                        "dosage": med.get("dosage", ""),
                        "reason": med.get("reason", ""),
                        "contraindications": med.get("contraindications", ""),
                        "notes": med.get("notes", ""),
                        "drugId": None,
                        "detailsUrl": None,
                        "imageUrl": None,
                        "hasMedia": False,
                    }

                    if drug_hit:
                        enriched["drugId"] = str(drug_hit.get("id"))
                        enriched["detailsUrl"] = (
                            f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/{drug_hit.get('id')}/details"
                        )
                        enriched["hasMedia"] = bool(drug_hit.get("hasMedia"))
                        if drug_hit.get("hasMedia"):
                            enriched["imageUrl"] = (
                                f"{settings.backend_url.rstrip('/')}/healthmate/api/drugs/{drug_hit.get('id')}/pack-image"
                            )

                    medications_enriched.append(enriched)

            log.info(
                "medications_enriched_complete",
                enriched_count=len(medications_enriched),
                names=[med.get("name") for med in medications_enriched[:10]],
                drug_ids=[med.get("drugId") for med in medications_enriched[:10]],
            )


            final_html = self._format_recommendation_html(
                recommendation_data, medications_enriched
            )
            log.info("html_formatted", html_len=len(final_html))


            from rag.medical.safety_checker import SafetyChecker

            safety = SafetyChecker()
            safety_warnings = safety.check_allergies(
                final_html,
                request.user_profile.allergies,
            )
            log.info("safety_check_complete", warnings=len(safety_warnings or []))

            await self._sessions.delete(session.session_id)

            elapsed = int((time.monotonic() - start) * 1000)
            log.info(
                "recommendation_generated",
                session_id=session.session_id,
                chunk_count=len(chunks),
                document_count=unique_doc_count,
                retrieval_top_k=settings.retrieval_top_k,
                processing_time_ms=elapsed,
                medication_count=len(medications_enriched),
                context_chars=current_context_size,
                context_usage_percent=round(current_context_size / MAX_CONTEXT_CHARS * 100, 1),
            )

            log.info(
                "response_to_java_before_send",
                session_id=session.session_id,
                recommended_drugs_count=len(medications_enriched),
                recommended_drugs_preview=[
                    {
                        "name": med.get("name"),
                        "drugId": med.get("drugId"),
                        "detailsUrl": med.get("detailsUrl"),
                    }
                    for med in medications_enriched[:5]
                ],
            )

            return QueryResponse(
                request_id=str(uuid.uuid4()),
                session_id=session.session_id,
                stage="recommendation",
                response_type="medical_recommendation",
                content={
                    "message": final_html,
                    "disclaimer": MEDICAL_DISCLAIMER,
                    "anamnesis_state": {"stage": "completed"},
                    "recommended_drugs": medications_enriched,
                    "recommendation_data": recommendation_data,
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

        except Exception as exc:
            log.error(
                "recommendation_generation_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                session_id=session.session_id,
                exc_traceback=repr(exc),
            )
            try:
                await self._sessions.delete(session.session_id)
            except Exception:
                pass

            return QueryResponse(
                request_id=str(uuid.uuid4()),
                session_id=session.session_id,
                stage="recommendation",
                response_type="medical_recommendation",
                content={
                    "message": f"Ошибка при обработке: {str(exc)[:80]}",
                    "disclaimer": MEDICAL_DISCLAIMER,
                    "anamnesis_state": {"stage": "completed"},
                    "recommended_drugs": [],
                    "recommendation_data": {},
                },
                context_used=ContextUsed(
                    retrieved_documents=[],
                    user_constraints_applied=[],
                    safety_checks_performed=["error"],
                ),
                next_action="session_complete",
                metadata=ResponseMetadata(
                    processing_time_ms=int((time.monotonic() - start) * 1000),
                    llm_model=settings.llm_model,
                    questions_asked=session.questions_asked,
                ),
            )

    def _format_recommendation_html(
        self, data: dict[str, Any], medications: list[dict[str, Any]]
    ) -> str:
        """Форматирует рекомендации в компактный HTML для фронтенда."""
        html_parts: list[str] = []

        intro = str(data.get("intro") or "").strip()
        if intro:
            html_parts.append(f"<p>{intro}</p>")

        if medications:
            html_parts.append("<p><strong>Подходящие препараты:</strong></p>")
            for med in medications:
                med_html = "<div style='margin:10px 0 12px; padding:10px 12px; border-left:4px solid #0066cc; background:#f9f9f9;'>"
                
                if med.get("detailsUrl"):
                    med_html += f"<strong><a href='{med['detailsUrl']}' target='_blank' style='color:#0066cc; text-decoration:none;'>{med['name']}</a></strong>"
                else:
                    med_html += f"<strong>{med['name']}</strong>"

                if med.get("imageUrl"):
                    med_html += f"<br/><img src='{med['imageUrl']}' alt='{med['name']}' style='max-height:70px; margin-top:8px; border-radius:4px;'/>"

                if med.get("dosage"):
                    med_html += f"<br/><span><strong>Дозировка:</strong> {med['dosage']}</span>"

                if med.get("reason"):
                    med_html += f"<br/><span><strong>Почему:</strong> {med['reason']}</span>"

                if med.get("contraindications"):
                    med_html += f"<br/><span style='color:#d9534f;'><strong>Осторожно:</strong> {med['contraindications']}</span>"

                if med.get("notes"):
                    med_html += f"<br/><em>{med['notes']}</em>"

                med_html += "</div>"
                html_parts.append(med_html)
        else:
            html_parts.append("<p><strong>Подходящих препаратов в базе не найдено.</strong></p>")

        if data.get("nonMedicalMeasures"):
            html_parts.append("<p><strong>Что можно сделать сейчас:</strong></p><ul>")
            for measure in list(data["nonMedicalMeasures"])[:3]:
                html_parts.append(f"<li>{measure}</li>")
            html_parts.append("</ul>")

        if data.get("warnings"):
            html_parts.append("<p style='color:#d9534f;'><strong>Важно:</strong></p><ul style='color:#d9534f;'>")
            for warning in list(data["warnings"])[:2]:
                html_parts.append(f"<li>{warning}</li>")
            html_parts.append("</ul>")

        if data.get("whenToSeekHelp"):
            html_parts.append(f"<p style='color:#d9534f;'><strong>Срочно к врачу:</strong> {data['whenToSeekHelp']}</p>")

        return "\n".join(html_parts) if html_parts else ""

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

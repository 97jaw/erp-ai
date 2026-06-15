"""SSE streaming handler for unified agent-mode endpoints."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from gateway.agent.constants import AGENT_MODEL
from gateway.agent.core import format_error
from gateway.agent.tools_registry import execute_tool, format_tool_result, get_all_tools
from gateway.agent.ui_blocks import normalize_ui_block
from gateway.agent.ui_block_tools import UI_TOOL_NAMES

logger = logging.getLogger(__name__)

MAX_ROUNDS_BY_TYPE = {
    "chat": 6,
    "audit": 6,
    "reports": 8,
}

TOOL_STATUS_LABELS = {
    "query_odoo": "Querying Odoo...",
    "aggregate_odoo": "Aggregating data...",
    "introspect_odoo_schema": "Checking schema...",
    "show_ui_block": "Preparing options...",
    "search_entities": "Searching records...",
    "search_fleet_vehicles": "Loading fleet vehicles...",
    "get_purchase_orders": "Looking up purchase orders...",
    "get_project_records": "Loading project records...",
    "list_attachments": "Loading documents...",
    "get_financial_report": "Loading financial report...",
    "get_trial_balance": "Loading trial balance...",
    "get_project_expense_summary": "Loading project expenses...",
    "compare_project_expenses": "Comparing projects...",
    "get_audit_trail": "Loading change history...",
    "get_user_activity": "Loading user activity...",
    "generate_report": "Generating report file...",
}


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def _ui_block_seen(blocks: list[dict[str, Any]], block: dict[str, Any]) -> bool:
    """Avoid duplicate picker blocks when Claude retries the same show_ui_block."""
    key = json.dumps(block, sort_keys=True, default=str)
    for existing in blocks:
        if json.dumps(existing, sort_keys=True, default=str) == key:
            return True
    return False


def _extract_text_from_message(response: Any) -> str:
    """Read assistant text blocks from the final API message."""
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            if text:
                parts.append(text)
    return "".join(parts).strip()


def _ui_block_prompt(ui_blocks: list[dict[str, Any]]) -> str:
    for block in ui_blocks:
        prompt = str(block.get("prompt") or "").strip()
        if prompt:
            return prompt
    return ""


def _resolve_final_text(
    *,
    streamed_text: str,
    last_response: Any | None,
    ui_blocks: list[dict[str, Any]],
    visualization: dict[str, Any] | None,
    tools_called: list[str],
    language: str,
    empty_fallback: str,
) -> str:
    """Prefer final-turn text; fall back when Claude ends on tools-only."""
    text = (streamed_text or "").strip()
    if not text and last_response is not None:
        text = _extract_text_from_message(last_response)
    if text:
        return text

    prompt = _ui_block_prompt(ui_blocks)
    if prompt:
        return prompt

    if visualization:
        title = str(visualization.get("title") or "").strip()
        if title:
            return title
        return "Here are the results." if language != "ar" else "إليك النتائج."

    data_tools = [name for name in tools_called if name not in UI_TOOL_NAMES]
    if data_tools:
        return (
            "I've gathered the data for you — see the details below."
            if language != "ar"
            else "جمعت البيانات — انظر التفاصيل أدناه."
        )

    return empty_fallback


def _detect_language(text: str) -> str:
    arabic_chars = sum(1 for char in text if "\u0600" <= char <= "\u06FF")
    if arabic_chars > len(text) * 0.3:
        return "ar"
    return "en"


def _progress_steps(agent_type: str, language: str) -> list[dict[str, str]]:
    if agent_type == "audit":
        if language == "ar":
            return [
                {"label": "فهم سؤال التدقيق", "status": "running"},
                {"label": "جلب سجل التغييرات", "status": "pending"},
                {"label": "إعداد الجدول الزمني", "status": "pending"},
            ]
        return [
            {"label": "Understanding your audit question", "status": "running"},
            {"label": "Fetching change history", "status": "pending"},
            {"label": "Preparing timeline", "status": "pending"},
        ]
    if agent_type == "reports":
        return []
    if language == "ar":
        return [
            {"label": "فهم السؤال", "status": "running"},
            {"label": "جلب البيانات", "status": "pending"},
            {"label": "إعداد الرد", "status": "pending"},
        ]
    return [
        {"label": "Understanding your question", "status": "running"},
        {"label": "Gathering data", "status": "pending"},
        {"label": "Preparing response", "status": "pending"},
    ]


def _status_message(agent_type: str, language: str, *, deep_think: bool = False) -> str:
    if agent_type == "audit":
        return "جاري تحليل سجل التدقيق..." if language == "ar" else "Analyzing audit trail..."
    if agent_type == "reports":
        return "جاري إعداد التقرير..." if language == "ar" else "Preparing report..."
    if deep_think:
        return (
            "تفكير عميق — جاري جلب البيانات..."
            if language == "ar"
            else "Deep thinking — pulling live data..."
        )
    return "جاري التفكير..." if language == "ar" else "Thinking..."


class AgentHandler:
    """Streams agent-mode responses via SSE."""

    def __init__(self, adapter: Any, agent_type: str = "chat") -> None:
        self.adapter = adapter
        self.agent_type = agent_type
        self.max_rounds = MAX_ROUNDS_BY_TYPE.get(agent_type, 6)

        from gateway.agent.core import get_async_client

        self.client = get_async_client()

    async def _build_messages(
        self,
        session_id: str,
        message: str,
        user: Any | None = None,
    ) -> list[dict[str, Any]]:
        if self.agent_type == "audit":
            from gateway.audit.memory import get_audit_history

            return [*get_audit_history(session_id), {"role": "user", "content": message}]
        if self.agent_type == "reports":
            from gateway.agent.reports_session import append_reports_message, get_reports_history

            append_reports_message(session_id, "user", message)
            return get_reports_history(session_id)
        from gateway.agent.conversation_persistence import load_claude_history
        from gateway.agent.session_state import get_session_history

        trimmed = message.strip()
        db_history = await load_claude_history(session_id, user)
        if db_history:
            if (
                db_history[-1].get("role") == "user"
                and str(db_history[-1].get("content") or "").strip() == trimmed
            ):
                return db_history
            return [*db_history, {"role": "user", "content": trimmed}]
        return [*get_session_history(session_id, last_n=5), {"role": "user", "content": trimmed}]

    async def _persist_turn(
        self,
        session_id: str,
        message: str,
        assistant_text: str,
        user: Any | None,
        *,
        language: str = "en",
        visualization: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        ui_blocks: list[dict[str, Any]] | None = None,
        response_time_ms: int | None = None,
    ) -> str | None:
        if self.agent_type == "audit":
            from gateway.audit.memory import append_audit_turn

            append_audit_turn(session_id, message, assistant_text)
            return None
        if self.agent_type == "reports":
            from gateway.agent.reports_session import append_reports_message

            if assistant_text:
                append_reports_message(session_id, "assistant", assistant_text)
            return None
        from gateway.agent.conversation_persistence import (
            append_assistant_message,
            sync_in_memory_turn,
        )

        sync_in_memory_turn(session_id, message, assistant_text)
        return await append_assistant_message(
            session_id,
            user,
            assistant_text,
            language=language,
            visualization=visualization,
            suggestions=suggestions,
            ui_blocks=ui_blocks,
            response_time_ms=response_time_ms,
        )

    async def handle_stream(
        self,
        message: str,
        user: Any | None,
        session_id: str,
        *,
        deep_think: bool = False,
        skip_clarification: bool = False,
        confirmed_entities: list[Any] | None = None,
        documents_scope: str | None = None,
    ) -> AsyncIterator[str]:
        language = _detect_language(message)
        effective_deep_think = deep_think
        if self.agent_type == "chat" and not effective_deep_think:
            from gateway.core.deep_think import is_deep_think_eligible

            if is_deep_think_eligible(message):
                effective_deep_think = True

        status = _status_message(self.agent_type, language, deep_think=effective_deep_think)
        yield _sse({"type": "status", "message": status})

        progress_steps = _progress_steps(self.agent_type, language)
        if progress_steps:
            yield _sse({"type": "progress", "steps": progress_steps})
            progress_steps[0]["status"] = "done"
            if len(progress_steps) > 1:
                progress_steps[1]["status"] = "running"
            yield _sse({"type": "progress", "steps": progress_steps})

        from gateway.agent.system_prompt import build_system_prompt

        turn_started = time.perf_counter()

        if self.agent_type == "chat" and session_id:
            from gateway.agent.session_entities import (
                apply_confirmed_entities,
                update_entities_from_message,
            )

            if confirmed_entities:
                apply_confirmed_entities(session_id, confirmed_entities)
            update_entities_from_message(session_id, message)

            from gateway.agent.intent_reconcile import reconcile_session_intent

            reconcile_session_intent(session_id, message)

            from gateway.agent.preflight import run_chat_preflight

            preflight = run_chat_preflight(
                message,
                session_id=session_id,
                language=language,
                skip_clarification=skip_clarification,
                confirmed_entities=confirmed_entities,
                user=user,
            )
            if preflight:
                if progress_steps:
                    for step in progress_steps:
                        step["status"] = "done"
                    yield _sse({"type": "progress", "steps": progress_steps})
                yield _sse({"type": "text", "chunk": preflight.text})
                for block in preflight.ui_blocks:
                    yield _sse({"type": "ui_block", "block": block})
                from gateway.agent.conversation_persistence import append_user_message

                await append_user_message(
                    session_id, user, message, language=language
                )
                conv_id = await self._persist_turn(
                    session_id,
                    message,
                    preflight.text,
                    user,
                    language=language,
                    ui_blocks=preflight.ui_blocks,
                    suggestions=preflight.suggestions,
                    response_time_ms=int((time.perf_counter() - turn_started) * 1000),
                )
                done_event: dict[str, Any] = {
                    "type": "done",
                    "text": preflight.text,
                    "session_id": session_id,
                    "conversation_id": conv_id or session_id,
                    "agent_type": self.agent_type,
                    "agent_mode": True,
                    "ui_blocks": preflight.ui_blocks,
                    "suggestions": preflight.suggestions,
                }
                yield _sse(done_event)
                return

            from gateway.agent.documents_flow import try_documents_flow

            documents = await try_documents_flow(
                message=message,
                user=user,
                adapter=self.adapter,
                session_id=session_id,
                language=language,
                skip_clarification=skip_clarification,
                confirmed_entities=confirmed_entities,
                documents_scope=documents_scope,
            )
            if documents:
                if progress_steps:
                    for step in progress_steps:
                        step["status"] = "done"
                    yield _sse({"type": "progress", "steps": progress_steps})
                yield _sse({"type": "text", "chunk": documents.text})
                for block in documents.ui_blocks:
                    yield _sse({"type": "ui_block", "block": block})
                from gateway.agent.conversation_persistence import append_user_message

                await append_user_message(session_id, user, message, language=language)
                conv_id = await self._persist_turn(
                    session_id,
                    message,
                    documents.text,
                    user,
                    language=language,
                    visualization=documents.visualization,
                    suggestions=documents.suggestions,
                    ui_blocks=documents.ui_blocks or None,
                    response_time_ms=int((time.perf_counter() - turn_started) * 1000),
                )
                documents_done: dict[str, Any] = {
                    "type": "done",
                    "text": documents.text,
                    "session_id": session_id,
                    "conversation_id": conv_id or session_id,
                    "agent_type": self.agent_type,
                    "agent_mode": True,
                    "visualization": documents.visualization,
                    "suggestions": documents.suggestions,
                    "tools_called": documents.tool_names,
                }
                if documents.ui_blocks:
                    documents_done["ui_blocks"] = documents.ui_blocks
                yield _sse(documents_done)
                return

            from gateway.agent.simple_query_fast_path import try_simple_query_fast_path

            simple = await try_simple_query_fast_path(
                message=message,
                user=user,
                adapter=self.adapter,
                language=language,
            )
            if simple:
                if progress_steps:
                    for step in progress_steps:
                        step["status"] = "done"
                    yield _sse({"type": "progress", "steps": progress_steps})
                yield _sse({"type": "text", "chunk": simple.text})
                from gateway.agent.conversation_persistence import append_user_message

                await append_user_message(session_id, user, message, language=language)
                conv_id = await self._persist_turn(
                    session_id,
                    message,
                    simple.text,
                    user,
                    language=language,
                    visualization=simple.visualization,
                    suggestions=simple.suggestions,
                    response_time_ms=int((time.perf_counter() - turn_started) * 1000),
                )
                simple_done: dict[str, Any] = {
                    "type": "done",
                    "text": simple.text,
                    "session_id": session_id,
                    "conversation_id": conv_id or session_id,
                    "agent_type": self.agent_type,
                    "agent_mode": True,
                    "visualization": simple.visualization,
                    "suggestions": simple.suggestions,
                    "tools_called": simple.tool_names,
                }
                yield _sse(simple_done)
                return

            from gateway.agent.attachment_fast_path import try_attachment_fast_path

            attachment = await try_attachment_fast_path(
                message=message,
                user=user,
                adapter=self.adapter,
                session_id=session_id,
                language=language,
            )
            if attachment:
                if progress_steps:
                    for step in progress_steps:
                        step["status"] = "done"
                    yield _sse({"type": "progress", "steps": progress_steps})
                yield _sse({"type": "text", "chunk": attachment.text})
                from gateway.agent.conversation_persistence import append_user_message

                await append_user_message(session_id, user, message, language=language)
                conv_id = await self._persist_turn(
                    session_id,
                    message,
                    attachment.text,
                    user,
                    language=language,
                    visualization=attachment.visualization,
                    suggestions=attachment.suggestions,
                    response_time_ms=int((time.perf_counter() - turn_started) * 1000),
                )
                attachment_done: dict[str, Any] = {
                    "type": "done",
                    "text": attachment.text,
                    "session_id": session_id,
                    "conversation_id": conv_id or session_id,
                    "agent_type": self.agent_type,
                    "agent_mode": True,
                    "visualization": attachment.visualization,
                    "suggestions": attachment.suggestions,
                    "tools_called": attachment.tool_names,
                }
                yield _sse(attachment_done)
                return

            from gateway.agent.financial_fast_path import try_financial_fast_path

            fast = await try_financial_fast_path(
                session_id=session_id,
                message=message,
                user=user,
                adapter=self.adapter,
                language=language,
            )
            if fast:
                if progress_steps:
                    for step in progress_steps:
                        step["status"] = "done"
                    yield _sse({"type": "progress", "steps": progress_steps})
                yield _sse({"type": "text", "chunk": fast.text})
                from gateway.agent.conversation_persistence import append_user_message

                await append_user_message(session_id, user, message, language=language)
                conv_id = await self._persist_turn(
                    session_id,
                    message,
                    fast.text,
                    user,
                    language=language,
                    visualization=fast.visualization,
                    suggestions=fast.suggestions,
                    response_time_ms=int((time.perf_counter() - turn_started) * 1000),
                )
                fast_done: dict[str, Any] = {
                    "type": "done",
                    "text": fast.text,
                    "session_id": session_id,
                    "conversation_id": conv_id or session_id,
                    "agent_type": self.agent_type,
                    "agent_mode": True,
                    "visualization": fast.visualization,
                    "suggestions": fast.suggestions,
                    "tools_called": fast.tool_names,
                }
                yield _sse(fast_done)
                return

            from gateway.agent.conversation_persistence import append_user_message

            await append_user_message(session_id, user, message, language=language)

        system_prompt = build_system_prompt(
            agent_type=self.agent_type,
            user=user,
            language=language,
            session_id=session_id,
        )
        tools = get_all_tools(agent_type=self.agent_type, user=user)
        messages = await self._build_messages(session_id, message, user)

        full_text_parts: list[str] = []
        round_text_parts: list[str] = []
        ui_blocks: list[dict[str, Any]] = []
        suggestions: list[dict[str, str]] = []
        visualization: dict[str, Any] | None = None
        tools_called: list[str] = []
        collected_tool_results: list[Any] = []
        audit_payloads: list[dict[str, Any]] = []
        file_results: list[dict[str, Any]] = []
        audit_data: dict[str, Any] | None = None
        last_response: Any | None = None

        try:
            for _round in range(self.max_rounds):
                stream_started = time.perf_counter()
                round_text_parts = []
                async with self.client.messages.stream(
                    model=AGENT_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        if not text:
                            continue
                        round_text_parts.append(text)
                        yield _sse({"type": "text", "chunk": text})

                    response = await stream.get_final_message()
                last_response = response

                from gateway.metrics import record_claude_response

                record_claude_response(
                    response,
                    time.perf_counter() - stream_started,
                    model=AGENT_MODEL,
                )

                if response.stop_reason == "end_turn":
                    full_text_parts = round_text_parts

                for block in response.content:
                    if block.type == "tool_use" and block.name in UI_TOOL_NAMES:
                        updated_viz = self._emit_ui_side_effects(
                            block.name,
                            dict(block.input or {}),
                            suggestions,
                            visualization,
                        )
                        if updated_viz is not None:
                            visualization = updated_viz

                if response.stop_reason == "end_turn":
                    break

                if response.stop_reason != "tool_use":
                    logger.warning(
                        "[AgentHandler] unexpected stop_reason=%s type=%s",
                        response.stop_reason,
                        self.agent_type,
                    )
                    break

                messages.append({"role": "assistant", "content": response.content})
                tool_result_blocks: list[dict[str, Any]] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    tools_called.append(block.name)
                    label = TOOL_STATUS_LABELS.get(block.name, f"Running {block.name}...")
                    yield _sse({"type": "status", "message": label})

                    try:
                        result = await execute_tool(
                            block.name,
                            dict(block.input or {}),
                            adapter=self.adapter,
                            user=user,
                            session_id=session_id,
                            user_message=message,
                        )
                        if block.name not in UI_TOOL_NAMES:
                            collected_tool_results.append(result)

                        for event in self._collect_side_effect_events(
                            block.name,
                            result,
                            audit_payloads=audit_payloads,
                            ui_blocks=ui_blocks,
                            file_results=file_results,
                        ):
                            if event.get("type") == "audit_data":
                                audit_data = event.get("audit_data")
                            yield _sse(event)

                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": format_tool_result(
                                    result,
                                    agent_type=self.agent_type,
                                ),
                            }
                        )
                    except Exception as exc:
                        logger.warning("[AgentHandler] tool %s failed: %s", block.name, exc)
                        error_payload = format_error(exc)
                        if block.name not in UI_TOOL_NAMES:
                            collected_tool_results.append(error_payload)
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(error_payload),
                                "is_error": True,
                            }
                        )

                if not tool_result_blocks:
                    logger.warning(
                        "[AgentHandler] tool_use stop with no tool_result blocks session=%s",
                        session_id,
                    )
                    break

                messages.append({"role": "user", "content": tool_result_blocks})
            else:
                logger.warning("[AgentHandler] max tool rounds session=%s", session_id)

            if progress_steps:
                for step in progress_steps[1:]:
                    step["status"] = "done"
                yield _sse({"type": "progress", "steps": progress_steps})

            clean_text = _resolve_final_text(
                streamed_text="".join(full_text_parts),
                last_response=last_response,
                ui_blocks=ui_blocks,
                visualization=visualization,
                tools_called=tools_called,
                language=language,
                empty_fallback=self._empty_response(language),
            )

            suggestion_labels = [s["label"] for s in suggestions]
            suggestion_details = list(suggestions)
            suggestion_meta: dict[str, Any] | None = None

            if self.agent_type == "chat":
                from gateway.agent.response_finalize import finalize_chat_response

                clean_text, visualization, suggestion_labels, suggestion_meta = (
                    finalize_chat_response(
                        clean_text,
                        visualization,
                        suggestion_labels,
                        tools_called,
                        collected_tool_results,
                        language,
                        message,
                        session_id,
                    )
                )
                suggestion_details = [
                    {"label": label, "query": label} for label in suggestion_labels
                ]
                if ui_blocks and clean_text.strip() == _ui_block_prompt(ui_blocks).strip():
                    clean_text = ""

            persist_text = clean_text
            if not persist_text.strip() and ui_blocks:
                persist_text = _ui_block_prompt(ui_blocks) or " "

            conv_id = await self._persist_turn(
                session_id,
                message,
                persist_text,
                user,
                language=language,
                visualization=visualization,
                suggestions=suggestion_labels,
                ui_blocks=ui_blocks or None,
                response_time_ms=int((time.perf_counter() - turn_started) * 1000),
            )

            if self.agent_type == "audit" and audit_data is None and audit_payloads:
                from gateway.agent.audit_helpers import audit_visualization_payload

                audit_data = audit_visualization_payload(audit_payloads)

            done_event: dict[str, Any] = {
                "type": "done",
                "text": clean_text,
                "session_id": session_id,
                "conversation_id": session_id,
                "agent_type": self.agent_type,
                "agent_mode": True,
            }

            if self.agent_type == "chat":
                from gateway.core.deep_think import is_deep_think_eligible

                done_event["conversation_id"] = conv_id or done_event.get("conversation_id")
                done_event.update(
                    {
                        "visualization": visualization,
                        "suggestions": suggestion_labels,
                        "suggestion_details": suggestion_details,
                        "ui_blocks": ui_blocks,
                        "tools_called": tools_called,
                        "deep_think_available": not effective_deep_think
                        and is_deep_think_eligible(message),
                    }
                )
                if suggestion_meta:
                    done_event["suggestion_meta"] = suggestion_meta
            elif self.agent_type == "audit":
                done_event.update(
                    {
                        "tools_called": tools_called,
                        "audit_data": audit_data,
                        "agent": "audit",
                        "ui_blocks": ui_blocks,
                        "suggestions": suggestion_labels,
                    }
                )
            elif self.agent_type == "reports":
                done_event.update(
                    {
                        "agent": "reports",
                        "ui_blocks": ui_blocks,
                        "files": file_results,
                    }
                )

            yield _sse(done_event)
        except Exception as exc:
            logger.exception("[AgentHandler] stream failed type=%s: %s", self.agent_type, exc)
            error_message = self._error_response(language)
            yield _sse({"type": "error", "message": error_message})
            yield _sse(
                {
                    "type": "done",
                    "text": error_message,
                    "session_id": session_id,
                    "agent_type": self.agent_type,
                    "agent": self.agent_type,
                    "agent_mode": True,
                }
            )

    def _empty_response(self, language: str) -> str:
        if self.agent_type == "audit":
            return (
                "لم أتمكن من إعداد استجابة التدقيق."
                if language == "ar"
                else "I could not prepare an audit response."
            )
        return "لم أتمكن من إعداد رد." if language == "ar" else "I could not prepare a response."

    def _error_response(self, language: str) -> str:
        if self.agent_type == "audit":
            return (
                "عذراً، حدث خطأ أثناء التدقيق. يرجى المحاولة مرة أخرى."
                if language == "ar"
                else "Sorry, I encountered an error while auditing. Please try again."
            )
        return (
            "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى."
            if language == "ar"
            else "Sorry, I encountered an error. Please try again."
        )

    def _collect_side_effect_events(
        self,
        tool_name: str,
        result: Any,
        *,
        audit_payloads: list[dict[str, Any]],
        ui_blocks: list[dict[str, Any]],
        file_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        if isinstance(result, dict) and result.get("status") == "ui_directive":
            data = result.get("data") or {}
            if tool_name == "show_ui_block":
                block = normalize_ui_block(data)
                if block and not _ui_block_seen(ui_blocks, block):
                    ui_blocks.append(block)
                    events.append({"type": "ui_block", "block": block})

        if self.agent_type == "audit" and tool_name in {"get_audit_trail", "get_user_activity"}:
            if isinstance(result, dict):
                audit_payloads.append({"tool": tool_name, "data": result})
                from gateway.agent.audit_helpers import audit_visualization_payload

                viz = audit_visualization_payload(audit_payloads)
                if viz:
                    events.append({"type": "audit_data", "audit_data": viz})

        if isinstance(result, dict):
            for event in result.get("_sse_events") or []:
                if event.get("type") == "file_ready_list":
                    files = event.get("files") or []
                    file_results.extend(files)
                events.append(event)

        return events

    def _emit_ui_side_effects(
        self,
        tool_name: str,
        data: dict[str, Any],
        suggestions: list[dict[str, str]],
        visualization: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Collect suggestions/viz from tool_use blocks. ui_blocks append after execute_tool."""
        if tool_name == "add_suggestions":
            for item in data.get("suggestions") or []:
                if isinstance(item, dict) and item.get("label"):
                    suggestions.append(
                        {
                            "label": str(item["label"]),
                            "query": str(item.get("query") or item["label"]),
                        }
                    )
        elif tool_name == "render_visualization":
            return dict(data)
        return visualization

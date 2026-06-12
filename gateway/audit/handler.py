"""Audit agent handler — /audit/stream endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Any, AsyncIterator

import anthropic

from gateway.audit.memory import append_audit_turn, get_audit_history
from gateway.audit.prompt import AUDIT_SYSTEM_PROMPT
from gateway.audit.tools import AUDIT_TOOL_DEFINITIONS, AUDIT_TOOL_EXECUTORS
from gateway.tools.universal_odoo import (
    UNIVERSAL_ODOO_EXECUTORS,
    UNIVERSAL_ODOO_TOOL_DEFINITIONS,
    build_universal_context,
)

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TOKENS = 4096
MAX_TOOL_ROUNDS = 6
TOOL_RESULT_CHAR_LIMIT = 12000

_UNIVERSAL_AUDIT_TOOLS = [
    tool
    for tool in UNIVERSAL_ODOO_TOOL_DEFINITIONS
    if tool["name"] in {"query_odoo", "aggregate_odoo"}
]

_AUDIT_TOOL_STATUS_LABELS = {
    "get_audit_trail": "Loading change history...",
    "get_user_activity": "Loading user activity...",
    "query_odoo": "Querying Odoo...",
    "aggregate_odoo": "Aggregating audit data...",
}

_async_client: anthropic.AsyncAnthropic | None = None


def _get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _async_client


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def _detect_language(text: str) -> str:
    arabic_chars = sum(1 for char in text if "\u0600" <= char <= "\u06FF")
    if arabic_chars > len(text) * 0.3:
        return "ar"
    return "en"


def _summarize_large_result(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    timeline = summary.get("timeline")
    if isinstance(timeline, list) and len(timeline) > 30:
        summary["timeline"] = timeline[:30]
        summary["_timeline_truncated"] = True
    by_model = summary.get("by_model")
    if isinstance(by_model, list):
        trimmed_models = []
        for group in by_model[:15]:
            if not isinstance(group, dict):
                continue
            group_copy = dict(group)
            records = group_copy.get("records")
            if isinstance(records, list) and len(records) > 10:
                group_copy["records"] = records[:10]
                group_copy["_records_truncated"] = True
            trimmed_models.append(group_copy)
        summary["by_model"] = trimmed_models
    records = summary.get("records")
    if isinstance(records, list) and len(records) > 50:
        summary["records"] = records[:50]
        summary["_records_truncated"] = True
    return summary


def _audit_visualization_payload(payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best structured payload for the audit UI (timeline vs activity)."""
    trail: dict[str, Any] | None = None
    activity: dict[str, Any] | None = None
    for item in payloads:
        data = item.get("data")
        if not isinstance(data, dict) or data.get("status") != "success":
            continue
        if item.get("tool") == "get_audit_trail":
            trail = data
        elif item.get("tool") == "get_user_activity":
            activity = data
    if trail:
        return {"view": "timeline", **trail}
    if activity:
        return {"view": "activity", **activity}
    return None


def _prepare_tool_result(result: Any) -> str:
    if isinstance(result, dict):
        result = _summarize_large_result(result)
    result_str = json.dumps(result, default=str)
    if len(result_str) > TOOL_RESULT_CHAR_LIMIT:
        result_str = result_str[:TOOL_RESULT_CHAR_LIMIT] + "..."
    return result_str


class AuditHandler:
    """Handles audit/analyze queries via Claude with audit tools."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.tools = [*AUDIT_TOOL_DEFINITIONS, *_UNIVERSAL_AUDIT_TOOLS]

    async def handle_stream(
        self,
        message: str,
        user: Any | None,
        session_id: str,
    ) -> AsyncIterator[str]:
        """Stream SSE events — same format as /chat/stream."""
        language = _detect_language(message)
        context = self._build_audit_context(user, session_id)

        status_message = (
            "جاري تحليل سجل التدقيق..."
            if language == "ar"
            else "Analyzing audit trail..."
        )
        yield _sse({"type": "status", "message": status_message})

        progress_steps = [
            {
                "label": "Understanding your audit question"
                if language == "en"
                else "فهم سؤال التدقيق",
                "status": "running",
            },
            {
                "label": "Fetching change history"
                if language == "en"
                else "جلب سجل التغييرات",
                "status": "pending",
            },
            {
                "label": "Preparing timeline"
                if language == "en"
                else "إعداد الجدول الزمني",
                "status": "pending",
            },
        ]
        yield _sse({"type": "progress", "steps": progress_steps})

        messages = self._build_messages(message, session_id)

        progress_steps[0]["status"] = "done"
        progress_steps[1]["status"] = "running"
        yield _sse({"type": "progress", "steps": progress_steps})

        system_prompt = self._build_system_prompt(context)
        full_text_parts: list[str] = []
        tools_called: list[str] = []
        audit_payloads: list[dict[str, Any]] = []

        try:
            for _round in range(MAX_TOOL_ROUNDS):
                stream_started = time.perf_counter()
                async with _get_async_client().messages.stream(
                    model=AGENT_MODEL,
                    max_tokens=MAX_AGENT_TOKENS,
                    system=system_prompt,
                    tools=self.tools,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        if not text:
                            continue
                        full_text_parts.append(text)
                        yield _sse({"type": "text", "chunk": text})

                    response = await stream.get_final_message()

                from gateway.metrics import record_claude_response

                record_claude_response(
                    response,
                    time.perf_counter() - stream_started,
                    model=AGENT_MODEL,
                )

                if response.stop_reason == "end_turn":
                    break

                if response.stop_reason != "tool_use":
                    logger.warning(
                        "[AuditHandler] unexpected stop_reason=%s", response.stop_reason
                    )
                    break

                messages.append({"role": "assistant", "content": response.content})
                tool_blocks = [block for block in response.content if block.type == "tool_use"]
                tool_results = []
                for block in tool_blocks:
                    tools_called.append(block.name)
                    label = _AUDIT_TOOL_STATUS_LABELS.get(
                        block.name,
                        f"Running {block.name}...",
                    )
                    yield _sse({"type": "status", "message": label})
                    result = await self._execute_tool(
                        block.name,
                        dict(block.input or {}),
                        user=user,
                        user_message=message,
                    )
                    if block.name in {"get_audit_trail", "get_user_activity"} and isinstance(
                        result, dict
                    ):
                        audit_payloads.append({"tool": block.name, "data": result})
                        viz = _audit_visualization_payload(audit_payloads)
                        if viz:
                            yield _sse({"type": "audit_data", "audit_data": viz})
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": _prepare_tool_result(result),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                logger.warning("[AuditHandler] max tool rounds reached session=%s", session_id)

            progress_steps[1]["status"] = "done"
            progress_steps[2]["status"] = "done"
            yield _sse({"type": "progress", "steps": progress_steps})

            clean_text = "".join(full_text_parts).strip()
            if not clean_text:
                clean_text = (
                    "لم أتمكن من إعداد استجابة التدقيق."
                    if language == "ar"
                    else "I could not prepare an audit response."
                )

            append_audit_turn(session_id, message, clean_text)

            audit_data = _audit_visualization_payload(audit_payloads)
            yield _sse(
                {
                    "type": "done",
                    "text": clean_text,
                    "session_id": session_id,
                    "conversation_id": session_id,
                    "tools_called": tools_called,
                    "audit_data": audit_data,
                    "agent": "audit",
                }
            )
        except Exception as exc:
            logger.exception("[AuditHandler] stream failed: %s", exc)
            error_message = (
                "عذراً، حدث خطأ أثناء التدقيق. يرجى المحاولة مرة أخرى."
                if language == "ar"
                else "Sorry, I encountered an error while auditing. Please try again."
            )
            yield _sse({"type": "error", "message": error_message})
            yield _sse(
                {
                    "type": "done",
                    "text": error_message,
                    "session_id": session_id,
                    "agent": "audit",
                }
            )

    def _build_audit_context(self, user: Any | None, session_id: str) -> dict[str, Any]:
        """Minimal context — user + temporal."""
        return {
            "user": user.to_dict() if user is not None and hasattr(user, "to_dict") else user,
            "today": date.today().isoformat(),
            "session_id": session_id,
        }

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        today = str(context.get("today") or date.today().isoformat())
        prompt = AUDIT_SYSTEM_PROMPT.replace("{today}", today)
        user = context.get("user")
        if user:
            prompt += f"\n\nAuthenticated user context:\n{json.dumps(user, default=str)}"
        return prompt

    def _build_messages(self, message: str, session_id: str) -> list[dict[str, Any]]:
        """Pass full audit session history plus the new user turn to Claude."""
        messages: list[dict[str, Any]] = get_audit_history(session_id)
        messages.append({"role": "user", "content": message})
        return messages

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        user: Any | None,
        user_message: str,
    ) -> Any:
        started = time.perf_counter()
        status = "success"
        try:
            if tool_name in AUDIT_TOOL_EXECUTORS:
                executor = AUDIT_TOOL_EXECUTORS[tool_name]
                if executor is None:
                    return {"status": "error", "message": f"Tool not wired: {tool_name}"}
                return await executor(self.adapter, tool_input, context=None)

            if tool_name in UNIVERSAL_ODOO_EXECUTORS:
                context = build_universal_context(user_message=user_message, user=user)
                return await UNIVERSAL_ODOO_EXECUTORS[tool_name](
                    self.adapter,
                    tool_input,
                    context,
                )

            status = "error"
            return {"status": "error", "message": f"Unknown audit tool: {tool_name}"}
        except Exception as exc:
            status = "error"
            logger.warning("[AuditHandler] tool %s failed: %s", tool_name, exc)
            return {"status": "error", "message": str(exc)}
        finally:
            from gateway.metrics import record_tool_execution

            record_tool_execution(
                tool_name=tool_name,
                duration_seconds=time.perf_counter() - started,
                status=status,
            )

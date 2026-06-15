"""The unified agent core — single tool-use loop replacing pipeline routing."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import anthropic

from gateway.agent.constants import AGENT_MODEL, MAX_AGENT_TOKENS
from gateway.agent.session_state import add_to_session, get_session_history
from gateway.agent.system_prompt import build_system_prompt
from gateway.agent.tools_registry import execute_tool, format_tool_result, get_all_tools

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6

_async_client: anthropic.AsyncAnthropic | None = None


def get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _async_client


@dataclass
class AgentResponse:
    """Structured agent output extracted from Claude's final turn."""

    text: str = ""
    ui_blocks: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[dict[str, str]] = field(default_factory=list)
    visualization: dict[str, Any] | None = None
    tools_called: list[str] = field(default_factory=list)


class Agent:
    """One agent loop for chat, audit, and reports."""

    def __init__(self, agent_type: str = "chat") -> None:
        self.agent_type = agent_type
        self.client = get_async_client()
        self.max_turns = MAX_TOOL_ROUNDS

    async def handle(
        self,
        message: str,
        *,
        user: Any | None,
        adapter: Any,
        session_id: str,
        language: str = "en",
    ) -> AgentResponse:
        """Run the agent loop and return the final structured response."""
        history = get_session_history(session_id, last_n=5)
        if self.agent_type == "chat":
            from gateway.agent.session_entities import update_entities_from_message

            update_entities_from_message(session_id, message)
        system_prompt = build_system_prompt(
            agent_type=self.agent_type,
            user=user,
            language=language,
            session_id=session_id,
        )
        tools = get_all_tools(agent_type=self.agent_type, user=user)
        messages: list[dict[str, Any]] = [*history, {"role": "user", "content": message}]

        collected = AgentResponse()
        response: Any = None

        for _turn in range(self.max_turns):
            response = await self.client.messages.create(
                model=AGENT_MODEL,
                max_tokens=MAX_AGENT_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            self._collect_from_response(response, collected)

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                logger.warning(
                    "[Agent] unexpected stop_reason=%s type=%s",
                    response.stop_reason,
                    self.agent_type,
                )
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = await self._execute_tool_blocks(
                response.content,
                collected=collected,
                adapter=adapter,
                user=user,
                session_id=session_id,
                user_message=message,
            )
            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("[Agent] max tool rounds reached session=%s", session_id)

        if response is not None:
            self._collect_text_from_response(response, collected)

        add_to_session(session_id, "user", message)
        add_to_session(session_id, "assistant", collected.text or "(no text)")

        return collected

    async def _execute_tool_blocks(
        self,
        content: list[Any],
        *,
        collected: AgentResponse,
        adapter: Any,
        user: Any | None,
        session_id: str,
        user_message: str,
    ) -> list[dict[str, Any]]:
        tool_results: list[dict[str, Any]] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            collected.tools_called.append(block.name)
            try:
                result = await execute_tool(
                    block.name,
                    dict(block.input or {}),
                    adapter=adapter,
                    user=user,
                    session_id=session_id,
                    user_message=user_message,
                )
                self._apply_ui_directive(block.name, result, collected)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": format_tool_result(result),
                    }
                )
            except Exception as exc:
                logger.warning("[Agent] tool %s failed: %s", block.name, exc)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(format_error(exc)),
                        "is_error": True,
                    }
                )
        return tool_results

    def _collect_from_response(self, response: Any, collected: AgentResponse) -> None:
        for block in response.content:
            if getattr(block, "type", None) == "text" and getattr(block, "text", ""):
                if block.text.strip():
                    collected.text = block.text.strip()
            elif getattr(block, "type", None) == "tool_use":
                self._apply_ui_directive(
                    block.name,
                    {"status": "ui_directive", "tool": block.name, "data": dict(block.input or {})},
                    collected,
                )

    def _collect_text_from_response(self, response: Any, collected: AgentResponse) -> None:
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text" and getattr(block, "text", ""):
                parts.append(block.text)
        if parts:
            collected.text = "".join(parts).strip()

    def _apply_ui_directive(
        self,
        tool_name: str,
        result: Any,
        collected: AgentResponse,
    ) -> None:
        if not isinstance(result, dict) or result.get("status") != "ui_directive":
            return
        data = result.get("data") or {}
        if tool_name == "show_ui_block":
            from gateway.agent.ui_blocks import normalize_ui_block

            block = normalize_ui_block(data)
            if block:
                collected.ui_blocks.append(block)
        elif tool_name == "add_suggestions":
            raw = data.get("suggestions") or []
            for item in raw:
                if isinstance(item, dict) and item.get("label"):
                    collected.suggestions.append(
                        {
                            "label": str(item["label"]),
                            "query": str(item.get("query") or item["label"]),
                        }
                    )
        elif tool_name == "render_visualization":
            collected.visualization = dict(data)


def format_error(error: Exception) -> dict[str, Any]:
    """Format errors so Claude can reason about them — never leak tracebacks to user."""
    error_msg = str(error)
    error_type = type(error).__name__

    if "Invalid field" in error_msg:
        return {
            "error_type": "invalid_field",
            "message": error_msg,
            "hint": (
                "The field doesn't exist on that model. "
                "Try introspect_odoo_schema to see valid fields."
            ),
        }
    if "permission" in error_msg.lower():
        return {
            "error_type": "permission_denied",
            "message": error_msg,
            "hint": "User lacks permission. Suggest an alternative or explain.",
        }
    return {
        "error_type": error_type,
        "message": error_msg,
        "hint": "Recover gracefully — explain to the user and suggest an alternative.",
    }

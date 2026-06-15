"""Post-process agent chat responses — viz + suggestions (shared with legacy chat path)."""

from __future__ import annotations

from typing import Any


def finalize_chat_response(
    clean_text: str,
    visualization: dict[str, Any] | None,
    suggestions: list[str],
    tool_names: list[str],
    tool_results: list[Any],
    language: str,
    user_message: str = "",
    session_id: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[str], dict[str, Any] | None]:
    """Apply visualization builder, suggestion pool, and response polish."""
    from gateway.main import _finalize_agent_response

    return _finalize_agent_response(
        clean_text,
        visualization,
        suggestions,
        tool_names,
        tool_results,
        language,
        user_message,
        session_id,
    )

"""Per-session conversation history for the reports agent."""

from __future__ import annotations

from typing import Any

_sessions: dict[str, list[dict[str, Any]]] = {}


def get_reports_history(session_id: str) -> list[dict[str, Any]]:
    return list(_sessions.get(session_id, []))


def append_reports_message(session_id: str, role: str, content: Any) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})


def clear_reports_session(session_id: str) -> None:
    _sessions.pop(session_id, None)

"""Lightweight conversation state for the unified agent loop."""

from __future__ import annotations

from typing import Any

MAX_TURNS = 10

_sessions: dict[str, list[dict[str, Any]]] = {}


def get_session_history(session_id: str, last_n: int = 5) -> list[dict[str, Any]]:
    """Return the last N user/assistant turns for a session."""
    history = _sessions.get(session_id, [])
    return history[-last_n * 2 :]


def add_to_session(session_id: str, role: str, content: Any) -> None:
    """Append one message to session history, trimming to MAX_TURNS."""
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})
    max_messages = MAX_TURNS * 2
    if len(_sessions[session_id]) > max_messages:
        _sessions[session_id] = _sessions[session_id][-max_messages:]


def clear_session(session_id: str) -> None:
    """Remove all history for a session."""
    _sessions.pop(session_id, None)

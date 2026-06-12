"""In-memory conversation history for the audit agent lane."""

from __future__ import annotations

from typing import Any

MAX_AUDIT_TURNS = 10

# session_id → list of {"role": "user"|"assistant", "content": str}
audit_sessions: dict[str, list[dict[str, Any]]] = {}


def get_audit_history(session_id: str) -> list[dict[str, Any]]:
    """Return a copy of stored turns for this audit session."""
    return list(audit_sessions.get(session_id, []))


def append_audit_turn(session_id: str, user_message: str, assistant_message: str) -> None:
    """Append one user/assistant pair and cap at the last MAX_AUDIT_TURNS turns."""
    history = audit_sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_message})
    max_messages = MAX_AUDIT_TURNS * 2
    if len(history) > max_messages:
        del history[: len(history) - max_messages]


def clear_audit_session(session_id: str) -> None:
    audit_sessions.pop(session_id, None)

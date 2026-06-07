"""In-memory Visualize agent sessions (Phase 2)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from visualize.prompt import DEFAULT_OUTPUT_ACTIONS


@dataclass
class VisualizeSession:
    session_id: str
    user_id: int | None
    dropped_items: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    output_type: str | None = None
    theme: str | None = None
    layout: str | None = None
    last_output: dict[str, Any] | None = None
    chat_session_id: str | None = None
    brain_inspection: dict[str, Any] | None = None
    brain_analysis: dict[str, Any] | None = None
    brain_recommendation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "dropped_items": self.dropped_items,
            "output_type": self.output_type,
            "theme": self.theme,
            "layout": self.layout,
            "last_output": self.last_output,
            "chat_session_id": self.chat_session_id,
            "message_count": len(self.messages),
            "brain_ready": bool(self.brain_recommendation),
        }


_lock = threading.Lock()
_sessions: dict[str, VisualizeSession] = {}


def create_session(
    *,
    user_id: int | None,
    items: list[dict[str, Any]],
    chat_session_id: str | None = None,
) -> VisualizeSession:
    session = VisualizeSession(
        session_id=str(uuid4()),
        user_id=user_id,
        dropped_items=list(items),
        chat_session_id=chat_session_id,
    )
    with _lock:
        _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> VisualizeSession | None:
    with _lock:
        return _sessions.get(session_id)


def update_session(session_id: str, **patch: Any) -> VisualizeSession | None:
    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return None
        for key, value in patch.items():
            if hasattr(session, key):
                setattr(session, key, value)
        return session


def append_message(session_id: str, role: str, content: str | list[Any]) -> None:
    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return
        session.messages.append({"role": role, "content": content})


def build_initial_greeting(items: list[dict[str, Any]]) -> str:
    """Short placeholder; the UI pre-fills build instructions from the analysis brain."""
    if not items:
        return ""
    return ""


def initial_response(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "greeting": build_initial_greeting(items),
        "actions": DEFAULT_OUTPUT_ACTIONS,
        "item_count": len(items),
    }

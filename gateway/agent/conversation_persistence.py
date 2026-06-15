"""Persist agent chat turns to ConversationStore (admin DB)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def append_user_message(
    session_id: str,
    user: Any | None,
    message: str,
    *,
    language: str = "en",
) -> None:
    """Record the user turn at stream start (updates last_message_at)."""
    user_id = getattr(user, "id", None) if user else None
    if not session_id or not user_id or not message.strip():
        return
    from gateway.conversation_store import ConversationStore

    try:
        await ConversationStore.append(
            session_id,
            "user",
            message.strip(),
            user_id=user_id,
            language=language,
        )
    except Exception as exc:
        logger.warning("[AgentPersist] user append failed session=%s: %s", session_id, exc)


async def append_assistant_message(
    session_id: str,
    user: Any | None,
    text: str,
    *,
    language: str = "en",
    visualization: dict[str, Any] | None = None,
    suggestions: list[str] | None = None,
    ui_blocks: list[dict[str, Any]] | None = None,
    response_time_ms: int | None = None,
) -> str | None:
    """Record assistant reply with optional viz, suggestions, and UI blocks."""
    user_id = getattr(user, "id", None) if user else None
    if not session_id or not user_id:
        return None
    from gateway.attachments.visualization import sanitize_visualization_for_persist

    cleaned = (text or "").strip()
    if not cleaned and not visualization and not ui_blocks:
        return None
    persist_visualization = sanitize_visualization_for_persist(visualization)
    from gateway.conversation_store import ConversationStore

    tool_calls = {"ui_blocks": ui_blocks} if ui_blocks else None
    try:
        await ConversationStore.append(
            session_id,
            "assistant",
            cleaned or " ",
            user_id=user_id,
            language=language,
            visualization=persist_visualization,
            suggestions=suggestions,
            tool_calls=tool_calls,
            response_time_ms=response_time_ms,
        )
        return ConversationStore.conversation_id_for_session(session_id)
    except Exception as exc:
        logger.warning("[AgentPersist] assistant append failed session=%s: %s", session_id, exc)
        return None


async def load_claude_history(
    session_id: str,
    user: Any | None,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Load recent turns for Claude from DB when available."""
    user_id = getattr(user, "id", None) if user else None
    if not session_id or not user_id:
        return []
    from gateway.conversation_store import ConversationStore

    try:
        raw = await ConversationStore.get(session_id, user_id=user_id)
        return _sanitize_claude_messages(raw)
    except Exception as exc:
        logger.warning("[AgentPersist] history load failed session=%s: %s", session_id, exc)
        return []


def _sanitize_claude_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip DB-only fields before sending history to Anthropic."""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = msg.get("content")
        if content is None:
            continue
        text = str(content).strip()
        if not text:
            continue
        cleaned.append({"role": role, "content": text})
    return cleaned


def sync_in_memory_turn(session_id: str, message: str, assistant_text: str) -> None:
    """Keep in-process session_state aligned for same-worker follow-ups."""
    from gateway.agent.session_state import add_to_session

    if message.strip():
        add_to_session(session_id, "user", message.strip())
    if assistant_text.strip():
        add_to_session(session_id, "assistant", assistant_text.strip())

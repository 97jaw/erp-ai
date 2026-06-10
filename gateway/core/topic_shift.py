"""Topic-shift detection — prevents stale entity reuse across conversation turns."""

from __future__ import annotations

import re
from typing import Any

from gateway.core.intent_analyzer import Intent

TOPIC_SHIFT_MARKERS_EN = (
    "now",
    "switch to",
    "change to",
    "instead",
    "different",
    "another",
    "next",
    "actually",
)
TOPIC_SHIFT_MARKERS_AR = (
    "الآن",
    "بدلا",
    "بدل",
    "مشروع آخر",
    "غير",
)

ENTITY_SCOPE_KEYS = (
    "project_id",
    "project_name",
    "confirmed_entities",
    "last_expense_summary_project_id",
    "partner_ids",
    "client_name",
    "project_ids",
)


def _normalize_entities(values: list[str]) -> set[str]:
    return {value.strip().lower() for value in values if value and value.strip()}


def _entities_overlap(current: set[str], previous: set[str]) -> bool:
    if not current or not previous:
        return False
    if current & previous:
        return True
    for current_value in current:
        for previous_value in previous:
            if current_value in previous_value or previous_value in current_value:
                return True
    return False


def _has_shift_marker(message: str) -> bool:
    lowered = message.lower().strip()
    for marker in TOPIC_SHIFT_MARKERS_EN:
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            return True
    for marker in TOPIC_SHIFT_MARKERS_AR:
        if marker in message:
            return True
    return False


def _is_pure_follow_up_turn(message: str, intent: Intent) -> bool:
    """Follow-up phrasing with no real new project reference is never a topic shift."""
    from gateway.core.project_expense_routing import FOLLOW_UP_SIGNALS, _is_real_project_reference

    query_lower = message.lower()
    has_followup_signal = any(signal in query_lower for signal in FOLLOW_UP_SIGNALS)
    if not has_followup_signal:
        return False

    project_entities = [entity for entity in intent.entities if entity.type == "project"]
    has_real_new_project = any(
        _is_real_project_reference(entity.value) for entity in project_entities
    )
    return not has_real_new_project


def detect_topic_shift(
    message: str,
    intent: Intent,
    *,
    last_turn: dict[str, Any] | None = None,
    active: Any | None = None,
) -> bool:
    """Return True when the current turn shifts away from the previous topic/entity."""
    if not last_turn:
        return False

    if _is_pure_follow_up_turn(message, intent):
        return False

    if active is not None:
        from gateway.core.project_expense_routing import is_followup_to_active

        if is_followup_to_active(message, intent, active):
            return False

    if _has_shift_marker(message):
        return True

    current_entities = _normalize_entities([entity.value for entity in intent.entities])
    last_entities = _normalize_entities(list(last_turn.get("entity_values") or []))
    if current_entities and last_entities and not _entities_overlap(current_entities, last_entities):
        return True

    last_subject = str(last_turn.get("subject_area") or "")
    if last_subject and intent.subject_area and last_subject != intent.subject_area:
        return True

    return False


def persist_last_turn(session_id: str, message: str, intent: Intent) -> None:
    """Store a snapshot of this turn for topic-shift detection on the next message."""
    if not session_id:
        return
    from gateway.session_scope import SessionScopeStore

    SessionScopeStore.update(
        session_id,
        last_turn={
            "message": message,
            "entity_values": [entity.value for entity in intent.entities],
            "subject_area": intent.subject_area,
        },
    )


def apply_topic_shift_clear(session_id: str, working_memory: Any) -> None:
    """Wipe entity scope from session store and in-memory working memory."""
    from gateway.session_scope import SessionScopeStore

    SessionScopeStore.clear_entity_scope(session_id)
    working_memory.clear_entity_context()

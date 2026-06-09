"""Tests for topic-shift detection (Phase F2)."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.topic_shift import (
    apply_topic_shift_clear,
    detect_topic_shift,
)
from gateway.core.working_memory import WorkingMemory
from gateway.session_scope import SessionScopeStore


def _make_intent(
    specific_intent: str,
    *,
    entities: list[str] | None = None,
    subject_area: str = "project",
) -> Intent:
    entity_refs = [
        EntityReference(type="project", value=value, confidence=0.9)
        for value in (entities or [])
    ]
    return Intent(
        primary_action="fetch_data",
        subject_area=subject_area,
        specific_intent=specific_intent,
        entities=entity_refs,
    )


def test_explicit_now_triggers_topic_shift() -> None:
    last_turn = {
        "message": "Villa 48 expense",
        "entity_values": ["Villa 48"],
        "subject_area": "project",
    }
    intent = _make_intent("now General maintenance work", entities=["General maintenance work"])

    assert detect_topic_shift("now General maintenance work", intent, last_turn=last_turn) is True


def test_no_entity_overlap_triggers_shift() -> None:
    last_turn = {
        "message": "Villa 48",
        "entity_values": ["Villa 48"],
        "subject_area": "project",
    }
    intent = _make_intent("Al Mushrif expense", entities=["Al Mushrif"])

    assert detect_topic_shift("Al Mushrif expense", intent, last_turn=last_turn) is True


def test_same_entity_no_shift_on_follow_up() -> None:
    last_turn = {
        "message": "Villa 48 expense",
        "entity_values": ["Villa 48"],
        "subject_area": "project",
    }
    intent = _make_intent("show me the breakdown", entities=[])

    assert detect_topic_shift("show me the breakdown", intent, last_turn=last_turn) is False


def test_working_memory_detect_topic_shift_delegates_to_last_turn() -> None:
    memory = WorkingMemory()
    memory.session_facts["last_turn"] = {
        "message": "Villa 48 expense",
        "entity_values": ["Villa 48"],
        "subject_area": "project",
    }
    intent = _make_intent("now General maintenance work", entities=["General maintenance work"])

    assert memory.detect_topic_shift("now General maintenance work", intent) is True


def test_clear_entity_context_wipes_session_entity_facts() -> None:
    memory = WorkingMemory()
    memory.remember_entity("project", {"id": 3288, "name": "Villa 48"})
    memory.session_facts["confirmed_entities"] = {"project": {"id": 3288, "name": "Villa 48"}}
    memory.session_facts["resolved_project_id"] = 3288
    memory.session_facts["last_expense_summary_project_id"] = 3288

    memory.clear_entity_context()

    assert memory.recent_entities == []
    assert "confirmed_entities" not in memory.session_facts
    assert "resolved_project_id" not in memory.session_facts


def test_apply_topic_shift_clear_wipes_session_scope() -> None:
    session_id = "topic-shift-clear-test"
    SessionScopeStore.update(
        session_id,
        project_id=3288,
        project_name="Villa 48",
        last_expense_summary_project_id=3288,
        confirmed_entities={"project": {"id": 3288, "name": "Villa 48"}},
        last_turn={"message": "Villa 48 expense", "entity_values": ["Villa 48"]},
    )
    memory = WorkingMemory()
    memory.session_facts["confirmed_entities"] = {"project": {"id": 3288, "name": "Villa 48"}}

    apply_topic_shift_clear(session_id, memory)

    scope = SessionScopeStore.get(session_id)
    assert "project_id" not in scope
    assert "confirmed_entities" not in scope
    assert scope.get("last_turn")  # prior turn snapshot kept for next comparison
    assert "confirmed_entities" not in memory.session_facts


@pytest.mark.asyncio
async def test_entity_gate_runs_after_topic_shift() -> None:
    """After topic shift, EntityGate must run instead of skipping on stale Villa scope."""
    from gateway.core.entity_gate import EntityGate
    from tests.core.test_context_stack import _make_context_stack

    context = _make_context_stack()
    context.working_memory.session_facts["last_turn"] = {
        "message": "Villa No. 48 expense this year",
        "entity_values": ["Villa No. 48"],
        "subject_area": "project",
    }
    context.working_memory.session_facts["resolved_project_id"] = 3288
    context.working_memory.session_facts["last_expense_summary_project_id"] = 3288
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 3288, "name": "Villa 48"},
    }

    apply_topic_shift_clear("topic-shift-gate", context.working_memory)

    message = "now General maintenance work"
    intent = _make_intent(message, entities=["General maintenance work"])

    assert EntityGate.intent_requires_entity_confirmation(message, intent, context) is True

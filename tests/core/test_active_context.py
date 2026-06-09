"""Tests for sticky project context (FIX 1) and follow-up detection (FIX 2)."""

from __future__ import annotations

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_expense_routing import is_followup_to_active
from gateway.core.working_memory import ActiveContext, WorkingMemory


def test_active_project_set_after_summary() -> None:
    mem = WorkingMemory()
    mem.set_active_project(15157, "Villa 34", confirmed=True)
    active = mem.get_active_project()
    assert active is not None
    assert active.project_id == 15157
    assert active.confirmed is True


def test_active_project_persists_until_switch() -> None:
    mem = WorkingMemory()
    mem.set_active_project(15157, "Villa 34")
    assert mem.get_active_project().project_id == 15157
    mem.clear_active_project()
    assert mem.get_active_project() is None


def _make_intent(text: str, entities: list[tuple[str, str]] | None = None) -> Intent:
    return Intent(
        primary_action="analyze",
        subject_area="project",
        specific_intent=text,
        entities=[
            EntityReference(type=entity_type, value=value, confidence=0.9)
            for entity_type, value in (entities or [])
        ],
    )


def test_breakdown_followup_uses_active() -> None:
    active = ActiveContext(project_id=15157, project_name="Villa 34", confirmed=True)
    intent = _make_intent("share the expense breakdown as well", entities=[])
    assert is_followup_to_active("share the expense breakdown as well", intent, active)


def test_project_id_as_entity_is_followup() -> None:
    active = ActiveContext(project_id=15157, project_name="Villa 34")
    intent = _make_intent("breakdown", entities=[("project", "15157")])
    assert is_followup_to_active("breakdown", intent, active)


def test_different_project_is_not_followup() -> None:
    active = ActiveContext(project_id=15157, project_name="Villa 34")
    intent = _make_intent("Al Mushrif expense", entities=[("project", "Al Mushrif")])
    assert not is_followup_to_active("Al Mushrif expense", intent, active)

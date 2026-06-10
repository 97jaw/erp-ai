"""Tests for is_followup_to_active phantom-entity fix."""

from __future__ import annotations

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_expense_routing import (
    _is_real_project_reference,
    is_followup_to_active,
)
from gateway.core.working_memory import ActiveContext


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


def intent_with_phantom(word: str) -> Intent:
    return _make_intent(word, entities=[("project", word)])


def intent_with_entity(name: str) -> Intent:
    return _make_intent(name, entities=[("project", name)])


VILLA34 = ActiveContext(project_id=15157, project_name="Villa 34", confirmed=True)


def test_phantom_breakdown_with_as_well_is_followup() -> None:
    assert is_followup_to_active(
        "give me breakdown as well",
        intent_with_phantom("breakdown"),
        VILLA34,
    )


def test_real_different_project_without_signal_is_not_followup() -> None:
    assert not is_followup_to_active(
        "Al Mushrif expense",
        intent_with_entity("Al Mushrif"),
        VILLA34,
    )


def test_active_project_name_entity_is_followup() -> None:
    assert is_followup_to_active(
        "breakdown of Villa 34",
        intent_with_entity("Villa 34"),
        VILLA34,
    )


def test_phantom_cost_with_breakdown_query_is_followup() -> None:
    assert is_followup_to_active(
        "show me the cost breakdown",
        intent_with_phantom("cost"),
        VILLA34,
    )


def test_phantom_expenses_with_as_well_is_followup() -> None:
    assert is_followup_to_active(
        "expenses as well",
        intent_with_phantom("expenses"),
        VILLA34,
    )


def test_is_real_project_reference_phantom_words() -> None:
    assert not _is_real_project_reference("breakdown")
    assert not _is_real_project_reference("expense")
    assert _is_real_project_reference("Al Mushrif")


def test_no_active_context_is_never_followup() -> None:
    assert not is_followup_to_active(
        "expenses as well",
        intent_with_phantom("expenses"),
        None,
    )


def test_real_project_switch_with_search_intent_is_not_followup() -> None:
    intent = Intent(
        primary_action="search_entity",
        subject_area="project",
        specific_intent="now show General maintenance projects",
        entities=[EntityReference(type="project", value="General maintenance", confidence=0.9)],
    )
    assert not is_followup_to_active("now show General maintenance projects", intent, VILLA34)

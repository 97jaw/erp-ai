"""Tests for follow-up gating topic-shift detection."""

from __future__ import annotations

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_expense_routing import is_followup_to_active
from gateway.core.topic_shift import detect_topic_shift
from gateway.core.working_memory import ActiveContext, WorkingMemory


def _intent(text: str, entities: list[tuple[str, str]] | None = None) -> Intent:
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
    return _intent(word, entities=[("project", word)])


VILLA34_ACTIVE = ActiveContext(project_id=15157, project_name="Villa Maintenance No. 34", confirmed=True)
VILLA34_LAST_TURN = {
    "message": "Villa 34 expense",
    "entity_values": ["Villa Maintenance No. 34"],
    "subject_area": "project",
}


def test_breakdown_as_well_is_followup_and_not_topic_shift() -> None:
    message = "give me breakdown as well"
    intent = intent_with_phantom("breakdown")

    assert is_followup_to_active(message, intent, VILLA34_ACTIVE) is True
    assert detect_topic_shift(message, intent, last_turn=VILLA34_LAST_TURN, active=VILLA34_ACTIVE) is False


def test_now_al_mushrif_is_not_followup_and_is_topic_shift() -> None:
    message = "now show Al Mushrif"
    intent = _intent(message, entities=[("project", "Al Mushrif")])

    assert is_followup_to_active(message, intent, VILLA34_ACTIVE) is False
    assert detect_topic_shift(message, intent, last_turn=VILLA34_LAST_TURN, active=VILLA34_ACTIVE) is True


def test_the_breakdown_too_is_followup_and_not_topic_shift() -> None:
    message = "the breakdown too"
    intent = _intent(message, entities=[])

    assert is_followup_to_active(message, intent, VILLA34_ACTIVE) is True
    assert detect_topic_shift(message, intent, last_turn=VILLA34_LAST_TURN, active=VILLA34_ACTIVE) is False


def test_pure_follow_up_phrase_blocks_topic_shift_without_active() -> None:
    message = "give me breakdown as well"
    intent = intent_with_phantom("breakdown")

    assert detect_topic_shift(message, intent, last_turn=VILLA34_LAST_TURN) is False


def test_now_al_mushrif_detects_topic_shift() -> None:
    message = "now Al Mushrif"
    intent = _intent(message, entities=[("project", "Al Mushrif")])

    assert detect_topic_shift(message, intent, last_turn=VILLA34_LAST_TURN) is True


def test_handler_order_keeps_active_on_follow_up() -> None:
    memory = WorkingMemory()
    memory.set_active_project(15157, "Villa Maintenance No. 34", confirmed=True)
    memory.session_facts["last_turn"] = VILLA34_LAST_TURN

    message = "give me breakdown as well"
    intent = intent_with_phantom("breakdown")
    active = memory.get_active_project()

    is_active_follow_up = is_followup_to_active(message, intent, active)
    topic_shift = False if is_active_follow_up else memory.detect_topic_shift(message, intent)

    assert is_active_follow_up is True
    assert topic_shift is False
    assert memory.get_active_project().project_id == 15157


def test_handler_order_clears_on_real_switch() -> None:
    memory = WorkingMemory()
    memory.set_active_project(15157, "Villa Maintenance No. 34", confirmed=True)
    memory.session_facts["last_turn"] = VILLA34_LAST_TURN
    memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }

    message = "now show Al Mushrif"
    intent = _intent(message, entities=[("project", "Al Mushrif")])
    active = memory.get_active_project()

    is_active_follow_up = is_followup_to_active(message, intent, active)
    topic_shift = False if is_active_follow_up else memory.detect_topic_shift(message, intent)

    assert is_active_follow_up is False
    assert topic_shift is True

    if topic_shift:
        memory.clear_entity_context()

    assert memory.get_active_project() is None

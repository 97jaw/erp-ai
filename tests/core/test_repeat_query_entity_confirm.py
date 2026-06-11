"""Tests for repeat-query entity clarification safety net."""

from __future__ import annotations

from gateway.core.entity_gate import ConfirmedEntityRef
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack


def test_repeat_query_applies_default_clarification_option() -> None:
    context = _make_context_stack()
    context.working_memory.session_facts["pending_entity_clarification"] = {
        "query": "expense for villa maintanence 37",
        "options": [
            {
                "id": "15158",
                "label": "Villa Maintenance No. 37 (WO: 1420240098-37)",
                "entity_type": "project",
                "entity_id": 15158,
                "action": "confirm_entity",
                "is_default": True,
            },
        ],
    }
    confirmed = IntelligentQueryHandler._try_repeat_query_entity_confirm(
        "expense for villa maintanence 37",
        context,
        None,
    )
    assert confirmed is not None
    assert len(confirmed) == 1
    assert confirmed[0].id == 15158
    assert confirmed[0].type == "project"


def test_repeat_query_ignored_when_message_differs() -> None:
    context = _make_context_stack()
    context.working_memory.session_facts["pending_entity_clarification"] = {
        "query": "expense for villa maintanence 37",
        "options": [
            {
                "entity_id": 15158,
                "action": "confirm_entity",
                "is_default": True,
            },
        ],
    }
    confirmed = IntelligentQueryHandler._try_repeat_query_entity_confirm(
        "expense for villa maintanence 34",
        context,
        None,
    )
    assert confirmed is None


def test_repeat_query_skipped_when_user_already_confirmed() -> None:
    context = _make_context_stack()
    existing = [ConfirmedEntityRef(type="project", id=99, name="Other")]
    confirmed = IntelligentQueryHandler._try_repeat_query_entity_confirm(
        "expense for villa maintanence 37",
        context,
        existing,
    )
    assert confirmed is existing

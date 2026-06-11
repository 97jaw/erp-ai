"""Tests for compare-mode multi-project entity gate (Fix B)."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import (
    EntityGate,
    ConfirmedEntityRef,
    dedupe_project_ids,
    extract_compare_project_queries,
    is_compare_project_intent,
)
from gateway.core.intent_analyzer import EntityReference, Intent
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import EntityResolver, MockProjectSearch


VILLA_COMPARE_CATALOG = [
    {
        "id": 15157,
        "name": "Villa Maintenance No. 34",
        "wo_ref_no": "WO-34",
        "description": "Villa 34 maintenance",
    },
    {
        "id": 15158,
        "name": "Villa Maintenance No. 43",
        "wo_ref_no": "WO-43",
        "description": "Villa 43 maintenance",
    },
]

ZAYIDIA_COMPARE_CATALOG = [
    {
        "id": 14549,
        "name": "Zayidia Boys School Renovation",
        "wo_ref_no": "WO-BOYS",
        "description": "Boys school",
    },
    {
        "id": 14610,
        "name": "Zayidia Girls School Renovation",
        "wo_ref_no": "WO-GIRLS",
        "description": "Girls school",
    },
]


def _compare_intent(*entities: tuple[str, str]) -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="compare project expenses",
        entities=[
            EntityReference(type="project", value=value, confidence=0.9)
            for value in entities
        ],
    )


def test_dedupe_project_ids_removes_duplicates() -> None:
    assert dedupe_project_ids([15157, 15157, 15158]) == [15157, 15158]
    assert dedupe_project_ids([15157, 0, -1, 15157]) == [15157]


def test_is_compare_project_intent_requires_two_projects() -> None:
    intent = _compare_intent("Villa 34", "Villa 43")
    assert is_compare_project_intent(intent)
    assert extract_compare_project_queries(intent) == ["Villa 34", "Villa 43"]

    single = Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="compare",
        entities=[EntityReference(type="project", value="Villa 34", confidence=0.9)],
    )
    assert not is_compare_project_intent(single)


@pytest.mark.asyncio
async def test_compare_villa_34_and_43_auto_confirms_both() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(VILLA_COMPARE_CATALOG))
    intent = _compare_intent("Villa 34", "Villa 43")
    context = _make_context_stack()

    result = await gate.evaluate(intent, context, "compare Villa 34 and Villa 43")

    assert result.status == "confirmed"
    assert result.compare_project_ids == [15157, 15158]
    assert context.working_memory.session_facts["compare_project_ids"] == [15157, 15158]
    assert len(context.working_memory.session_facts["compare_resolved_projects"]) == 2


@pytest.mark.asyncio
async def test_compare_zayidia_boys_and_girls_auto_confirms() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(ZAYIDIA_COMPARE_CATALOG))
    intent = _compare_intent("Zayidia Boys School", "Zayidia Girls School")
    context = _make_context_stack()

    result = await gate.evaluate(
        intent,
        context,
        "compare Zayidia Boys and Girls",
    )

    assert result.status == "confirmed"
    assert result.compare_project_ids == [14549, 14610]


@pytest.mark.asyncio
async def test_compare_accepts_two_confirmed_entities_at_once() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(VILLA_COMPARE_CATALOG))
    intent = _compare_intent("Villa 34", "Villa 43")
    context = _make_context_stack()

    result = await gate.evaluate(
        intent,
        context,
        "compare Villa 34 and Villa 43",
        confirmed_entities=[
            ConfirmedEntityRef(type="project", id=15157, name="Villa Maintenance No. 34"),
            ConfirmedEntityRef(type="project", id=15158, name="Villa Maintenance No. 43"),
        ],
    )

    assert result.status == "confirmed"
    assert result.compare_project_ids == [15157, 15158]


@pytest.mark.asyncio
async def test_compare_one_clear_one_ambiguous_shows_pending_slot() -> None:
    catalog = [
        *VILLA_COMPARE_CATALOG,
        {
            "id": 9991,
            "name": "Villa Maintenance No. 43 Phase 2",
            "wo_ref_no": "WO-43B",
            "description": "Second villa 43 match",
        },
    ]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog))
    intent = _compare_intent("Villa 34", "Villa 43")
    context = _make_context_stack()

    result = await gate.evaluate(intent, context, "compare Villa 34 and Villa 43")

    assert result.status == "needs_confirmation"
    assert result.compare_pending_query == "Villa 43"
    assert len(result.compare_resolved_projects) == 1
    assert result.compare_resolved_projects[0]["id"] == 15157
    assert len(result.options) >= 2


@pytest.mark.asyncio
async def test_compare_second_confirm_completes_pair() -> None:
    catalog = [
        *VILLA_COMPARE_CATALOG,
        {
            "id": 9991,
            "name": "Villa Maintenance No. 43 Phase 2",
            "wo_ref_no": "WO-43B",
            "description": "Second villa 43 match",
        },
    ]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog))
    intent = _compare_intent("Villa 34", "Villa 43")
    context = _make_context_stack()
    context.working_memory.session_facts["compare_resolved_projects"] = [
        {"query": "Villa 34", "id": 15157, "name": "Villa Maintenance No. 34"},
    ]
    context.working_memory.session_facts["compare_pending_query"] = "Villa 43"

    result = await gate.evaluate(
        intent,
        context,
        "compare Villa 34 and Villa 43",
        confirmed_entities=[
            ConfirmedEntityRef(type="project", id=15158, name="Villa Maintenance No. 43"),
        ],
    )

    assert result.status == "confirmed"
    assert result.compare_project_ids == [15157, 15158]


@pytest.mark.asyncio
async def test_execute_compare_project_expenses_deduplicates_duplicate_ids() -> None:
    from gateway.tools.project_expense import execute_compare_project_expenses
    from tests.core.test_project_expense_tools import MockAdapter, _summary_odoo_payload

    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 15157): _summary_odoo_payload(
                project_name="Villa 34",
                expenses=100_000,
            ),
            ("get_project_expense_summary_mobile", 15158): _summary_odoo_payload(
                project_name="Villa 43",
                expenses=200_000,
            ),
        },
    )
    result = await execute_compare_project_expenses(
        {"project_ids": [15157, 15157, 15158]},
        adapter,
        None,
    )
    assert result["status"] == "success"
    assert sorted(item["project_id"] for item in result["projects"]) == [15157, 15158]

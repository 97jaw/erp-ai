"""Phase E2 — project expense tool selection for 15 canonical query phrasings."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_expense_routing import select_project_expense_tool
from tests.core.test_context_stack import _make_context_stack


def _intent(
    message: str,
    *,
    primary_action: str = "fetch_data",
    subject_area: str = "project",
    entities: list[EntityReference] | None = None,
) -> Intent:
    return Intent(
        primary_action=primary_action,
        subject_area=subject_area,
        specific_intent=message,
        entities=entities or [],
        estimated_complexity="simple",
    )


def _context(**facts: Any):
    stack = _make_context_stack()
    stack.working_memory.session_facts.update(facts)
    if facts.get("project_id") and not facts.get("confirmed_entities"):
        stack.working_memory.session_facts["confirmed_entities"] = {
            "project": {
                "id": facts["project_id"],
                "name": facts.get("project_name", "Zayidia Boys School"),
            },
        }
    return stack


ZAYIDIA_BOYS = 14549
ZAYIDIA_GIRLS = 14610


@pytest.mark.parametrize(
    ("case_id", "message", "intent_kwargs", "context_facts", "expected_tool", "expected_input"),
    [
        (
            1,
            "show me Zayidia Boys School costs",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            2,
            "Zayidia Boys School expense overview",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            3,
            "how much did we spend on Zayidia",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            4,
            "is Zayidia over budget",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            5,
            "break down Zayidia by account",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            6,
            "show GL details for Zayidia",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            7,
            "where exactly did money go",
            {},
            {"last_expense_summary_project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            8,
            "compare Boys and Girls Zayidia",
            {"primary_action": "compare", "entities": [
                EntityReference(type="project", value="Zayidia Boys School", confidence=0.9),
                EntityReference(type="project", value="Zayidia Girls School", confidence=0.9),
            ]},
            {"compare_project_ids": [ZAYIDIA_BOYS, ZAYIDIA_GIRLS]},
            "compare_project_expenses",
            {"project_ids": [ZAYIDIA_BOYS, ZAYIDIA_GIRLS]},
        ),
        (
            9,
            "which Zayidia project is over budget",
            {"primary_action": "compare"},
            {"compare_project_ids": [ZAYIDIA_BOYS, ZAYIDIA_GIRLS]},
            "compare_project_expenses",
            {"project_ids": [ZAYIDIA_BOYS, ZAYIDIA_GIRLS]},
        ),
        (
            10,
            "drill into materials for Boys School",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS, "main_group_filter": "materials"},
        ),
        (
            11,
            "show full breakdown",
            {},
            {"last_expense_summary_project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            12,
            "expenses for project 14549",
            {},
            {},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            13,
            "تكاليف مشروع زايديا",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            14,
            "what's the spend status of Zayidia Boys",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            15,
            "tell me about Zayidia Boys School money",
            {},
            {"project_id": ZAYIDIA_BOYS},
            "get_project_expense_summary",
            {"project_id": ZAYIDIA_BOYS},
        ),
        (
            16,
            "show me cost break down as well",
            {},
            {"last_expense_summary_project_id": ZAYIDIA_BOYS, "project_id": ZAYIDIA_BOYS},
            "get_project_expense_breakdown",
            {"project_id": ZAYIDIA_BOYS},
        ),
    ],
    ids=[f"case_{index}" for index in range(1, 17)],
)
def test_project_expense_tool_selection(
    case_id: int,
    message: str,
    intent_kwargs: dict[str, Any],
    context_facts: dict[str, Any],
    expected_tool: str,
    expected_input: dict[str, Any],
) -> None:
    del case_id
    intent = _intent(message, **intent_kwargs)
    context = _context(**context_facts)
    selected = select_project_expense_tool(message, intent, context)
    assert selected is not None
    tool_name, tool_input = selected
    assert tool_name == expected_tool
    assert tool_input == expected_input


def test_system_prompt_includes_project_expense_section() -> None:
    from gateway.main import _compose_system_prompt_sections

    prompt = _compose_system_prompt_sections("Monday, 09 June 2026")
    assert "PROJECT EXPENSE QUERY HANDLING" in prompt
    assert "get_project_expense_summary" in prompt
    assert "get_project_expense_breakdown" in prompt
    assert "compare_project_expenses" in prompt
    assert "W.O amount" in prompt


@pytest.mark.asyncio
async def test_strategy_planner_routes_summary_for_project_costs() -> None:
    from gateway.core.entity_gate import EntityGate
    from gateway.core.strategy_planner import StrategyPlanner

    context = _context(project_id=ZAYIDIA_BOYS)
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": ZAYIDIA_BOYS, "name": "Zayidia Boys School"},
    }
    assert EntityGate.project_confirmed(context)

    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    intent = _intent("show me Zayidia Boys School costs")
    strategy = planner.plan_simple(intent, context)
    assert strategy.steps[0].tool == "get_project_expense_summary"
    assert strategy.steps[0].tool_input == {"project_id": ZAYIDIA_BOYS}


def test_infer_entity_hints_rewrites_financial_expense_to_project() -> None:
    from gateway.core.entity_gate import EntityGate

    intent = _intent(
        "Villa Maintenance No. 34 expense",
        subject_area="financial",
        primary_action="fetch_data",
        entities=[
            EntityReference(type="project", value="Villa Maintenance No. 34", confidence=0.9),
        ],
    )
    updated = EntityGate.infer_entity_hints("Villa Maintenance No. 34 expense", intent)
    assert updated.subject_area == "project"
    assert updated.primary_action == "fetch_data"


@pytest.mark.asyncio
async def test_strategy_planner_routes_villa_expense_with_financial_subject() -> None:
    from gateway.core.entity_gate import EntityGate
    from gateway.core.strategy_planner import StrategyPlanner

    context = _context(project_id=31034, project_name="Villa Maintenance No. 34")
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 31034, "name": "Villa Maintenance No. 34"},
    }
    assert EntityGate.project_confirmed(context)

    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    intent = _intent(
        "Villa Maintenance No. 34 expense",
        subject_area="financial",
        primary_action="fetch_data",
        entities=[
            EntityReference(type="project", value="Villa Maintenance No. 34", confidence=0.9),
        ],
    )
    intent = EntityGate.infer_entity_hints("Villa Maintenance No. 34 expense", intent)
    strategy = planner.plan_simple(intent, context)
    assert strategy.steps[0].tool == "get_project_expense_summary"
    assert strategy.steps[0].tool_input == {"project_id": 31034}

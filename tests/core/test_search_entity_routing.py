"""Tests for search_entity routing (Phase F3)."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import EntityGate
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.strategy_planner import StrategyPlanner
from tests.core.test_context_stack import _make_context_stack


def _search_intent(
    *,
    hint: str = "General maintenance work",
    specific_intent: str = "search_for_general_maintenance_projects",
) -> Intent:
    return Intent(
        primary_action="search_entity",
        subject_area="project",
        specific_intent=specific_intent,
        entities=[EntityReference(type="project", value=hint, confidence=0.9)],
        estimated_complexity="simple",
    )


@pytest.mark.asyncio
async def test_search_entity_action_routes_to_search() -> None:
    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    context = _make_context_stack()
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 3288, "name": "Villa 48"},
    }
    context.working_memory.session_facts["resolved_project_id"] = 3288

    strategy = await planner.plan(_search_intent(), context)

    assert strategy.steps[0].tool == "search_entities"
    assert strategy.steps[0].tool != "get_project_expense_summary"
    assert strategy.steps[0].tool_input["query"] == "General maintenance work"
    assert strategy.synthesis_approach == "present_candidates"


def test_infer_entity_hints_preserves_search_entity_on_expense_query() -> None:
    intent = Intent(
        primary_action="search_entity",
        subject_area="general",
        specific_intent="General maintenance work expense report",
        entities=[EntityReference(type="project", value="General maintenance work", confidence=0.9)],
    )
    updated = EntityGate.infer_entity_hints(
        "General maintenance work need expense report",
        intent,
    )
    assert updated.primary_action == "search_entity"


@pytest.mark.asyncio
async def test_expense_query_with_fetch_data_still_routes_to_summary() -> None:
    from gateway.core.entity_gate import EntityGate
    from tests.core.test_project_expense_routing import _context, _intent

    context = _context(project_id=31034, project_name="Villa Maintenance No. 34")
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 31034, "name": "Villa Maintenance No. 34"},
    }
    assert EntityGate.project_confirmed(context)

    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    intent = _intent("Villa Maintenance No. 34 expense")
    strategy = planner.plan_simple(intent, context)
    assert strategy.steps[0].tool == "get_project_expense_summary"


@pytest.mark.asyncio
async def test_generate_report_al_mushrif_with_stale_villa_scope_routes_search() -> None:
    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    context = _make_context_stack()
    context.working_memory.session_facts["resolved_project_id"] = 15157
    context.working_memory.session_facts["project_name"] = "Villa Maintenance No. 34"
    context.working_memory.session_facts["last_expense_summary_project_id"] = 15157

    intent = Intent(
        primary_action="generate_report",
        subject_area="project",
        specific_intent="generate_expense_report_for_project",
        entities=[
            EntityReference(
                type="project",
                value="Al Mushrif general maintenance work",
                confidence=0.8,
            ),
        ],
        estimated_complexity="moderate",
    )

    strategy = await planner.plan(intent, context)

    assert strategy.steps[0].tool == "search_entities"
    assert "Al Mushrif" in strategy.steps[0].tool_input["query"]


@pytest.mark.asyncio
async def test_generate_report_confirmed_project_routes_to_expense_summary() -> None:
    from tests.core.test_project_expense_routing import _context

    planner = StrategyPlanner(client=object())  # type: ignore[arg-type]
    context = _context(project_id=15157, project_name="Villa Maintenance No. 34")
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }

    intent = Intent(
        primary_action="generate_report",
        subject_area="project",
        specific_intent="generate expense report for Villa Maintenance No. 34",
        entities=[
            EntityReference(
                type="project",
                value="Villa Maintenance No. 34",
                confidence=0.9,
            ),
        ],
        estimated_complexity="moderate",
    )

    strategy = await planner.plan(intent, context)

    assert strategy.steps[0].tool == "get_project_expense_summary"
    assert strategy.steps[0].tool_input["project_id"] == 15157

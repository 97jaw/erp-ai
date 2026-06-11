"""Integration tests for compare-mode entity gate → compare_project_expenses."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import dedupe_project_ids
from gateway.core.entity_resolver import EntityResolver
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_entity_gate_compare import VILLA_COMPARE_CATALOG, ZAYIDIA_COMPARE_CATALOG
from tests.core.test_entity_resolver import MockProjectSearch
from tests.core.test_execution_orchestrator import MockToolExecutor
from tests.integration.test_intelligent_handler import (
    FixedContextStackBuilder,
    FixedIntentAnalyzer,
    StubProactiveIntelligence,
    _stack_for_user,
    _super_admin,
)


@pytest.mark.asyncio
async def test_compare_villa_34_and_43_runs_compare_tool() -> None:
    intent = Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="compare Villa 34 and Villa 43 expenses",
        entities=[
            EntityReference(type="project", value="Villa 34", confidence=0.9),
            EntityReference(type="project", value="Villa 43", confidence=0.9),
        ],
        expected_output="table",
    )
    executor = MockToolExecutor(
        responses={
            ("compare_project_expenses", 1): {
                "status": "success",
                "_source": "compare_project_expenses",
                "projects": [
                    {"project_id": 15157, "project_name": "Villa Maintenance No. 34", "total_expenses": 1000},
                    {"project_id": 15158, "project_name": "Villa Maintenance No. 43", "total_expenses": 2000},
                ],
            },
        },
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(_stack_for_user(_super_admin())),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch(VILLA_COMPARE_CATALOG)),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        "compare Villa 34 and Villa 43",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
    )

    assert not response.awaiting_clarification
    assert response.tools_called == ["compare_project_expenses"]
    assert executor.calls
    project_ids = executor.calls[0][1].get("project_ids") or []
    assert dedupe_project_ids([int(pid) for pid in project_ids]) == [15157, 15158]
    assert len(set(project_ids)) == 2


@pytest.mark.asyncio
async def test_compare_zayidia_boys_and_girls_runs_compare_tool() -> None:
    intent = Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="compare Zayidia Boys and Girls",
        entities=[
            EntityReference(type="project", value="Zayidia Boys School", confidence=0.9),
            EntityReference(type="project", value="Zayidia Girls School", confidence=0.9),
        ],
        expected_output="table",
    )
    executor = MockToolExecutor(
        responses={
            ("compare_project_expenses", 1): {
                "status": "success",
                "_source": "compare_project_expenses",
                "projects": [
                    {"project_id": 14549, "project_name": "Zayidia Boys School Renovation"},
                    {"project_id": 14610, "project_name": "Zayidia Girls School Renovation"},
                ],
            },
        },
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(_stack_for_user(_super_admin())),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch(ZAYIDIA_COMPARE_CATALOG)),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        "compare Zayidia Boys and Girls",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
    )

    assert not response.awaiting_clarification
    assert "compare_project_expenses" in response.tools_called
    project_ids = executor.calls[0][1]["project_ids"]
    assert dedupe_project_ids([int(pid) for pid in project_ids]) == [14549, 14610]


def test_compare_project_ids_never_contains_duplicates_from_routing() -> None:
    from gateway.core.project_expense_routing import select_project_expense_tool

    intent = Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="compare Villa 34 and Villa 43",
        entities=[
            EntityReference(type="project", value="Villa 34", confidence=0.9),
            EntityReference(type="project", value="Villa 43", confidence=0.9),
        ],
    )
    stack = _stack_for_user(_super_admin())
    stack.working_memory.set_active_project(15157, "Villa Maintenance No. 34", confirmed=True)
    stack.working_memory.session_facts["compare_project_ids"] = [15157, 15158]

    selected = select_project_expense_tool("compare Villa 34 and Villa 43", intent, stack)
    assert selected is not None
    tool_name, tool_input = selected
    assert tool_name == "compare_project_expenses"
    assert dedupe_project_ids(tool_input["project_ids"]) == [15157, 15158]
    assert len(set(tool_input["project_ids"])) == 2

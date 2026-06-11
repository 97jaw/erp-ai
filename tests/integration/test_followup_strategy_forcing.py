"""Follow-up must force expense tools with active project_id, not search_entities."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from gateway.core.context_stack import ContextStack, ConversationContext
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.entity_resolver import EntityResolver
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.proactive_intelligence import ProactiveActions, ProactiveIntelligence
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch
from tests.core.test_execution_orchestrator import MockToolExecutor
from tests.integration.test_intelligent_handler import _super_admin


class FixedIntentAnalyzer:
    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    async def analyze(self, query: str, context: ContextStack) -> Intent:
        del query, context
        return self.intent


class ActiveProjectContextBuilder(ContextStackBuilder):
    def __init__(self, stack: ContextStack) -> None:
        self._stack = stack

    async def build(self, user: Any, request: Any) -> ContextStack:
        del user
        return replace(
            self._stack,
            conversation=ConversationContext(
                session_id=getattr(request, "session_id", None),
                message=getattr(request, "message", ""),
            ),
        )


class StubProactiveIntelligence(ProactiveIntelligence):
    async def anticipate(self, synthesized: Any, intent: Intent, context: ContextStack) -> ProactiveActions:
        del synthesized, intent, context
        return ProactiveActions()

    def schedule_precompute(self, proactive: ProactiveActions, **kwargs: Any) -> ProactiveActions:
        del kwargs
        return proactive


def _stack_with_active_villa34() -> ContextStack:
    stack = _make_context_stack()
    stack.working_memory.set_active_project(15157, "Villa Maintenance No. 34", confirmed=True)
    return stack


@pytest.mark.asyncio
async def test_breakdown_followup_forces_expense_tool_not_search_entities() -> None:
    """Turn 2 with active=15157 must call get_project_expense_breakdown, not search_entities."""
    message = "show me breakdown as well"
    intent = Intent(
        primary_action="analyze",
        subject_area="project",
        specific_intent="get_project_expense_breakdown",
        entities=[EntityReference(type="project", value="15157", confidence=0.9)],
        expected_output="table",
        estimated_complexity="moderate",
    )
    executor = MockToolExecutor(
        responses={
            ("get_project_expense_breakdown", 1): {
                "status": "success",
                "project_id": 15157,
                "project_name": "Villa Maintenance No. 34",
                "currency": "AED",
                "grand_total": 11053.15,
                "group_count": 1,
                "groups": [
                    {
                        "code": "MG01",
                        "name": "Salary",
                        "total": 11053.15,
                        "subgroups": [],
                    },
                ],
                "_source": "project_expense_breakdown_mobile",
            },
        },
    )
    handler = IntelligentQueryHandler(
        context_builder=ActiveProjectContextBuilder(_stack_with_active_villa34()),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch([])),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        message,
        _super_admin(),
        adapter=object(),
        executor=executor,
        session_id="followup-force-breakdown",
    )

    tools_called = [call[0] for call in executor.calls]
    assert "search_entities" not in tools_called
    assert response.tools_called == ["get_project_expense_breakdown"]
    assert executor.calls[0][1].get("project_id") == 15157
    assert (response.visualization or {}).get("visual_type") == "PROJECT_EXPENSE_BREAKDOWN"

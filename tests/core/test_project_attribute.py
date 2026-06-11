"""Tests for FIX 6 — non-financial project attribute handling."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import EntityReference, Intent, IntentAnalyzer
from gateway.core.project_attribute_utils import is_project_attribute_query
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_intent_analyzer import MockJsonClient, _intent_json
from tests.integration.test_intelligent_handler import (
    FixedContextStackBuilder,
    FixedIntentAnalyzer,
    StubProactiveIntelligence,
    _super_admin,
)


def test_pm_question_is_attribute_not_financial() -> None:
    assert is_project_attribute_query("who is the project manager of Villa 34")


@pytest.mark.asyncio
async def test_analyzer_marks_pm_question_as_project_attribute() -> None:
    analyzer = IntentAnalyzer(
        client=MockJsonClient(
            _intent_json(
                subject_area="project",
                primary_action="fetch_data",
                specific_intent="who is the project manager of Villa 34",
            ),
        ),
    )
    context = _make_context_stack()
    intent = await analyzer.analyze("who is the project manager of Villa 34", context)
    assert intent.subject_area == "project_attribute"
    assert intent.primary_action == "ask_question"


def test_expense_question_is_not_attribute() -> None:
    assert not is_project_attribute_query("Villa 34 expense for this year")


class _ProfileStubAdapter:
    """Adapter exposing only the project profile read used by the new lane."""

    def read_project_profile(self, project_id: int) -> dict:
        assert project_id == 15157
        return {
            "id": 15157,
            "name": "Villa Maintenance No. 34",
            "user_id": [1060, "Mohammed W E Abuyousef"],
            "projects_manager": [881, "Hassan Mohamed M Abuebeid"],
        }


@pytest.mark.asyncio
async def test_attribute_question_served_by_profile_lane() -> None:
    """Project Model Phase 1: PM questions are now answered from the project
    header (no Deep Think) instead of the old honest deferral."""
    stack = _make_context_stack()
    stack.working_memory.set_active_project(15157, "Villa Maintenance No. 34", confirmed=True)
    intent = Intent(
        primary_action="ask_question",
        subject_area="project_attribute",
        specific_intent="who is the PM of Villa 34",
        entities=[EntityReference(type="project", value="Villa 34", confidence=0.9)],
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(stack),
        intent_analyzer=FixedIntentAnalyzer(intent),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        "who is the PM of Villa 34",
        _super_admin(),
        adapter=_ProfileStubAdapter(),
        session_id="attr-test",
    )

    lowered = response.text.lower()
    assert "mohammed w e abuyousef" in lowered
    assert "don't have access" not in lowered
    assert not response.awaiting_clarification
    assert response.tools_called == ["get_project_profile"]


@pytest.mark.asyncio
async def test_attribute_question_without_project_keeps_deferral() -> None:
    """No project reference anywhere — the honest deferral remains."""
    stack = _make_context_stack()
    intent = Intent(
        primary_action="ask_question",
        subject_area="project_attribute",
        specific_intent="who is the manager",
        entities=[],
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(stack),
        intent_analyzer=FixedIntentAnalyzer(intent),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        "who is the manager",
        _super_admin(),
        adapter=object(),
        session_id="attr-test-2",
    )

    lowered = response.text.lower()
    assert "don't have access" in lowered
    assert response.tools_called == []

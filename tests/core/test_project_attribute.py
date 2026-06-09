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


@pytest.mark.asyncio
async def test_attribute_question_honest_response() -> None:
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
        adapter=object(),
        session_id="attr-test",
    )

    lowered = response.text.lower()
    assert "manager" in lowered
    assert "odoo" in lowered or "coming soon" in lowered
    assert "financial data for" not in lowered
    assert not response.awaiting_clarification
    assert response.tools_called == []

"""Tests for gateway.core.intent_analyzer.IntentAnalyzer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import AnalyzerException, Intent, IntentAnalyzer
from tests.core.test_context_stack import _make_context_stack


class MockJsonClient:
    """Mock Claude JSON client for analyzer tests."""

    def __init__(
        self,
        response: str | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.complete_json = AsyncMock(side_effect=self._complete_json)

    async def _complete_json(self, *, model: str, prompt: str) -> str:
        if self.error is not None:
            raise self.error
        assert model
        assert prompt
        return self.response or "{}"


def _intent_json(**overrides: object) -> str:
    payload = {
        "primary_action": "fetch_data",
        "subject_area": "financial",
        "specific_intent": "Show profit and loss",
        "entities": [],
        "implicit_requirements": [],
        "ambiguities": [],
        "expected_output": "summary",
        "urgency": "normal",
        "estimated_complexity": "simple",
        "requires_clarification": False,
        "clarification_question": None,
        "out_of_scope": False,
        "out_of_scope_reason": None,
    }
    payload.update(overrides)
    return json.dumps(payload)


async def _analyze(
    query: str,
    mock_response: str,
    *,
    primary_role: str = "regular_user",
    level: int = 30,
) -> Intent:
    analyzer = IntentAnalyzer(client=MockJsonClient(mock_response))
    context = _make_context_stack(primary_role=primary_role, level=level)
    context.conversation.message = query
    return await analyzer.analyze(query, context)


@pytest.mark.asyncio
async def test_analyze_returns_intent_object() -> None:
    intent = await _analyze("show me p&l", _intent_json())
    assert isinstance(intent, Intent)


@pytest.mark.asyncio
async def test_show_me_pandl_primary_action_fetch_data() -> None:
    intent = await _analyze("show me p&l", _intent_json(primary_action="fetch_data"))
    assert intent.primary_action == "fetch_data"


@pytest.mark.asyncio
async def test_show_me_pandl_subject_area_financial() -> None:
    intent = await _analyze("show me p&l", _intent_json(subject_area="financial"))
    assert intent.subject_area == "financial"


@pytest.mark.asyncio
async def test_payslip_query_out_of_scope_true() -> None:
    intent = await _analyze(
        "what is my payslip",
        _intent_json(
            primary_action="fetch_data",
            subject_area="hr",
            specific_intent="Retrieve payslip",
            out_of_scope=True,
            out_of_scope_reason="hr.payslips is unavailable in the assistant",
        ),
    )
    assert intent.out_of_scope is True


@pytest.mark.asyncio
async def test_payslip_query_out_of_scope_reason_mentions_hr_or_payroll() -> None:
    intent = await _analyze(
        "what is my payslip",
        _intent_json(
            subject_area="hr",
            out_of_scope=True,
            out_of_scope_reason="hr.payslips is unavailable; use HR portal",
        ),
    )
    reason = (intent.out_of_scope_reason or "").lower()
    assert "hr" in reason or "payroll" in reason or "payslip" in reason


@pytest.mark.asyncio
async def test_national_guard_project_entities_contains_project_reference() -> None:
    intent = await _analyze(
        "national guard project",
        _intent_json(
            subject_area="project",
            specific_intent="Find National Guard project",
            entities=[
                {
                    "type": "project",
                    "value": "National Guard",
                    "confidence": 0.91,
                }
            ],
        ),
    )
    assert any(entity.type == "project" for entity in intent.entities)


@pytest.mark.asyncio
async def test_json_parse_error_returns_safe_fallback_intent() -> None:
    analyzer = IntentAnalyzer(client=MockJsonClient("this is not json"))
    context: ContextStack = _make_context_stack()
    intent = await analyzer.analyze("show me p&l", context)
    assert isinstance(intent, Intent)
    assert intent.primary_action == "other"
    assert intent.requires_clarification is True
    assert intent.clarification_question is not None


@pytest.mark.asyncio
async def test_claude_api_error_raises_analyzer_exception_with_clear_message() -> None:
    analyzer = IntentAnalyzer(
        client=MockJsonClient(error=RuntimeError("connection reset")),
    )
    context = _make_context_stack()

    with pytest.raises(AnalyzerException, match="Claude intent analysis failed"):
        await analyzer.analyze("show me p&l", context)


@pytest.mark.asyncio
async def test_super_admin_common_query_requires_clarification_false() -> None:
    intent = await _analyze(
        "show trial balance for last month",
        _intent_json(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent="Show trial balance for last month",
            requires_clarification=False,
        ),
        primary_role="super_admin",
        level=100,
    )
    assert intent.requires_clarification is False


@pytest.mark.asyncio
async def test_vague_query_requires_clarification_true() -> None:
    intent = await _analyze(
        "how are we doing",
        _intent_json(
            primary_action="analyze",
            subject_area="general",
            specific_intent="Assess overall business performance",
            requires_clarification=True,
            clarification_question="Which area should I focus on: finance, projects, or operations?",
        ),
    )
    assert intent.requires_clarification is True


@pytest.mark.asyncio
async def test_complete_query_with_date_range_requires_clarification_false() -> None:
    intent = await _analyze(
        "show p&l for january to march 2026",
        _intent_json(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent="Show P&L for January to March 2026",
            entities=[
                {"type": "period", "value": "2026-01-01 to 2026-03-31", "confidence": 0.98}
            ],
            requires_clarification=False,
        ),
    )
    assert intent.requires_clarification is False

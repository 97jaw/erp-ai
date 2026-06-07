"""Tests for gateway.core.strategy_planner."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from gateway.core.intent_analyzer import Intent
from gateway.core.strategy_planner import StrategyException, StrategyPlanner
from tests.core.test_context_stack import _make_context_stack


class MockJsonClient:
    """Mock Claude JSON client for strategy planner tests."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.complete_json = AsyncMock(return_value=response)


def _simple_pandl_intent() -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show P&L for last 3 months",
        estimated_complexity="simple",
    )


def _complex_compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="project",
        specific_intent="Compare National Guard and Zayidia Boys School project expenses",
        entities=[],
        estimated_complexity="complex",
        expected_output="chart",
    )


def _complex_strategy_json() -> str:
    payload = {
        "steps": [
            {
                "step_number": 1,
                "description": "Resolve National Guard project",
                "tool": "search_odoo",
                "tool_input": {"model": "project.project", "query": "National Guard"},
                "depends_on": [],
                "parallel_with": [],
                "expected_output": "records",
                "fallback_if_fails": "Use get_projects_summary with broader search",
            },
            {
                "step_number": 2,
                "description": "Fetch National Guard project expenses",
                "tool": "get_project_expenses",
                "tool_input": {"project_name": "National Guard"},
                "depends_on": [1],
                "parallel_with": [3],
                "expected_output": "summary",
                "fallback_if_fails": "Use get_project_financial_data with date range",
            },
            {
                "step_number": 3,
                "description": "Fetch Zayidia Boys School project expenses",
                "tool": "get_project_expenses",
                "tool_input": {"project_name": "Zayidia Boys School"},
                "depends_on": [1],
                "parallel_with": [2],
                "expected_output": "summary",
                "fallback_if_fails": "Use search_odoo to locate project then retry",
            },
        ],
        "synthesis_approach": "Compare expense totals and highlight the larger cost drivers",
        "quality_checks": [
            "Both project expense totals are present",
            "Comparison uses the same date range",
        ],
        "estimated_duration_ms": 4500,
    }
    return json.dumps(payload)


def _revenue_compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        estimated_complexity="complex",
        expected_output="chart",
    )


@pytest.mark.asyncio
async def test_revenue_by_client_last_quarter_uses_single_step_strategy() -> None:
    planner = StrategyPlanner(client=MockJsonClient("{}"))
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="show me revenue by client last quarter",
        estimated_complexity="simple",
        expected_output="table",
    )
    strategy = await planner.plan(intent, _make_context_stack())
    assert len(strategy.steps) == 1
    assert strategy.steps[0].tool == "group_and_aggregate"


@pytest.mark.asyncio
async def test_revenue_comparison_uses_deterministic_two_step_strategy() -> None:
    planner = StrategyPlanner(client=MockJsonClient("{}"))
    strategy = await planner.plan(_revenue_compare_intent(), _make_context_stack())
    assert len(strategy.steps) == 2
    assert strategy.steps[0].tool == "group_and_aggregate"
    assert strategy.steps[1].tool == "group_and_aggregate"
    assert strategy.steps[0].parallel_with == [2]
    assert strategy.steps[0].tool_input["group_by"] == ["partner_id"]
    assert strategy.steps[0].tool_input["date_from"] == "2026-01-01"
    assert strategy.steps[1].tool_input["date_from"] == "2025-01-01"


@pytest.mark.asyncio
async def test_simple_pandl_intent_strategy_has_one_step() -> None:
    planner = StrategyPlanner(client=MockJsonClient("{}"))
    strategy = await planner.plan(_simple_pandl_intent(), _make_context_stack())
    assert len(strategy.steps) == 1


@pytest.mark.asyncio
async def test_simple_intent_step_has_correct_tool_name() -> None:
    planner = StrategyPlanner(client=MockJsonClient("{}"))
    strategy = await planner.plan(_simple_pandl_intent(), _make_context_stack())
    assert strategy.steps[0].tool == "get_financial_report"


@pytest.mark.asyncio
async def test_complex_comparison_intent_strategy_has_three_or_more_steps() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert len(strategy.steps) >= 3


@pytest.mark.asyncio
async def test_complex_strategy_steps_have_depends_on_populated() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    dependent_steps = [step for step in strategy.steps if step.step_number > 1]
    assert dependent_steps
    assert all(step.depends_on for step in dependent_steps)


@pytest.mark.asyncio
async def test_parallel_steps_have_parallel_with_populated() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    parallel_steps = [step for step in strategy.steps if step.parallel_with]
    assert len(parallel_steps) >= 2


@pytest.mark.asyncio
async def test_strategy_has_non_empty_quality_checks() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert strategy.quality_checks
    assert all(check.strip() for check in strategy.quality_checks)


@pytest.mark.asyncio
async def test_all_steps_have_fallback_if_fails_set() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert all(step.fallback_if_fails.strip() for step in strategy.steps)


@pytest.mark.asyncio
async def test_strategy_has_synthesis_approach_description() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert strategy.synthesis_approach.strip()


@pytest.mark.asyncio
async def test_estimated_duration_ms_is_positive_integer() -> None:
    planner = StrategyPlanner(client=MockJsonClient(_complex_strategy_json()))
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert isinstance(strategy.estimated_duration_ms, int)
    assert strategy.estimated_duration_ms > 0


@pytest.mark.asyncio
async def test_invalid_intent_raises_strategy_exception_clearly() -> None:
    planner = StrategyPlanner(client=MockJsonClient("{}"))
    invalid_intent = Intent(
        primary_action="",
        subject_area="financial",
        specific_intent="Show P&L",
    )
    with pytest.raises(StrategyException, match="primary_action is required"):
        await planner.plan(invalid_intent, _make_context_stack())


@pytest.mark.asyncio
async def test_complex_strategy_retries_on_invalid_json() -> None:
    class FlakyJsonClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete_json(self, *, model: str, prompt: str, max_tokens: int = 800) -> str:
            self.calls += 1
            if self.calls == 1:
                return '{"steps":[{"step_number":1,"description":"broken'
            return _complex_strategy_json()

    client = FlakyJsonClient()
    planner = StrategyPlanner(client=client)
    strategy = await planner.plan(_complex_compare_intent(), _make_context_stack())
    assert client.calls == 2
    assert len(strategy.steps) >= 3

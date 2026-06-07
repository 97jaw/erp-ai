"""Tests for gateway.core.execution_orchestrator retry and fallback handling."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.execution_orchestrator import ExecutionOrchestrator, OrchestrationException
from gateway.core.strategy_planner import ExecutionStep, Strategy
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_execution_orchestrator import MockToolExecutor, _strategy


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt_after_exception() -> None:
    executor = MockToolExecutor(fail_attempts={"group_and_aggregate": 1})
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch revenue",
            tool="group_and_aggregate",
            tool_input={"model": "account.move"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert result.results[1]["ok"] is True
    assert executor._attempt_counts["group_and_aggregate"] == 2
    assert result.failures == []


@pytest.mark.asyncio
async def test_retry_broadens_search_on_empty_result() -> None:
    executor = MockToolExecutor(empty_attempts={"search_odoo": 1})
    executor.responses[("search_odoo", 2)] = {"rows": [{"id": 1}]}
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Search partners",
            tool="search_odoo",
            tool_input={"model": "res.partner", "limit": 10, "partner_id": 5},
            fallback_if_fails="use_tool:search_odoo:{'model': 'res.partner'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert result.results[1]["rows"] == [{"id": 1}]
    assert executor.calls[1][1]["broadened"] is True
    assert "partner_id" not in executor.calls[1][1]


def test_parse_fallback_spec_parses_use_tool_format() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    tool, tool_input = orchestrator._parse_fallback_spec(
        "use_tool:search_odoo:{'model': 'account.move', 'limit': 20}",
    )

    assert tool == "search_odoo"
    assert tool_input == {"model": "account.move", "limit": 20}


@pytest.mark.asyncio
async def test_fallback_executes_alternate_tool_on_primary_failure() -> None:
    executor = MockToolExecutor(fail_tools={"group_and_aggregate"})
    executor.responses[("search_odoo", 3)] = {"rows": [{"id": 99}]}
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch revenue",
            tool="group_and_aggregate",
            tool_input={"model": "account.move"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert result.results[1]["rows"] == [{"id": 99}]
    assert ("search_odoo", {"model": "account.move"}) in executor.calls
    assert result.failures == []


@pytest.mark.asyncio
async def test_fallback_success_logs_fallback_status() -> None:
    executor = MockToolExecutor(fail_tools={"group_and_aggregate"})
    executor.responses[("search_odoo", 3)] = {"rows": [{"id": 1}]}
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch revenue",
            tool="group_and_aggregate",
            tool_input={"model": "account.move"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert any(entry.status == "failed" for entry in result.orchestration_log)
    assert any(entry.status == "fallback" for entry in result.orchestration_log)


@pytest.mark.asyncio
async def test_fallback_failure_marks_step_failed_and_continues() -> None:
    executor = MockToolExecutor(fail_tools={"group_and_aggregate", "search_odoo"})
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch revenue",
            tool="group_and_aggregate",
            tool_input={"model": "account.move"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
        ExecutionStep(
            step_number=2,
            description="Compose report",
            tool="compose_report",
            tool_input={"report_type": "comparison"},
            depends_on=[],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert 1 not in result.results
    assert 2 in result.results
    assert len(result.failures) == 1
    assert result.failures[0].step.step_number == 1


def test_is_empty_or_invalid_detects_error_and_empty_rows() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())

    assert orchestrator._is_empty_or_invalid(None) is True
    assert orchestrator._is_empty_or_invalid({"error": "boom"}) is True
    assert orchestrator._is_empty_or_invalid({"rows": []}) is True
    assert orchestrator._is_empty_or_invalid({"rows": [{"id": 1}]}) is False


def test_broaden_search_increases_limit_and_drops_narrow_filters() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    broadened = orchestrator._broaden_search(
        "search_odoo",
        {
            "model": "account.move",
            "limit": 10,
            "partner_id": 7,
            "date_from": "2026-01-01",
        },
    )

    assert broadened["limit"] == 50
    assert broadened["broadened"] is True
    assert "partner_id" not in broadened
    assert "date_from" not in broadened


def test_broaden_search_preserves_project_id_for_entity_bound_tools() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    broadened = orchestrator._broaden_search(
        "get_project_expenses",
        {
            "project_id": 201,
            "project_name": "Zayidia Boys School Renovation",
            "date_from": "2026-01-01",
            "date_to": "2026-06-30",
        },
    )

    assert broadened["project_id"] == 201
    assert broadened["project_name"] == "Zayidia Boys School Renovation"
    assert "date_from" not in broadened
    assert "date_to" not in broadened


def test_invalid_fallback_spec_raises_orchestration_exception() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())

    with pytest.raises(OrchestrationException, match="Invalid fallback spec"):
        orchestrator._parse_fallback_spec("Retry with broader search")

"""Tests for gateway.core.execution_orchestrator execution scheduling."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from gateway.core.context_stack import ContextStack
from gateway.core.execution_orchestrator import (
    ExecutionOrchestrator,
    OrchestrationException,
    VariableResolutionError,
)
from gateway.core.strategy_planner import ExecutionStep, Strategy
from tests.core.test_context_stack import _make_context_stack


class MockToolExecutor:
    """Records tool calls and simulates optional latency or failures."""

    def __init__(
        self,
        responses: dict[tuple[str, int], Any] | None = None,
        *,
        delay_seconds: float = 0.0,
        fail_tools: set[str] | None = None,
        fail_attempts: dict[str, int] | None = None,
        empty_attempts: dict[str, int] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.delay_seconds = delay_seconds
        self.fail_tools = fail_tools or set()
        self.fail_attempts = fail_attempts or {}
        self.empty_attempts = empty_attempts or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.concurrent = 0
        self.max_concurrent = 0
        self._attempt_counts: dict[str, int] = {}

    async def execute(
        self,
        tool: str,
        tool_input: dict[str, Any],
        context: ContextStack,
    ) -> Any:
        attempt = self._attempt_counts.get(tool, 0) + 1
        self._attempt_counts[tool] = attempt
        self.calls.append((tool, tool_input))
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        self.concurrent -= 1
        if tool in self.fail_tools:
            raise RuntimeError(f"{tool} failed")
        if attempt <= self.fail_attempts.get(tool, 0):
            raise RuntimeError(f"{tool} failed on attempt {attempt}")
        if attempt <= self.empty_attempts.get(tool, 0):
            return {"rows": []}
        return self.responses.get((tool, len(self.calls)), {"ok": True, "tool": tool})


def _strategy(*steps: ExecutionStep, quality_checks: list[str] | None = None) -> Strategy:
    return Strategy(
        steps=list(steps),
        synthesis_approach="Test synthesis",
        quality_checks=quality_checks or ["Results present"],
        estimated_duration_ms=1000,
    )


@pytest.mark.asyncio
async def test_single_step_executes_sequentially() -> None:
    executor = MockToolExecutor({("get_financial_report", 1): {"total": 1000}})
    orchestrator = ExecutionOrchestrator(executor)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch P&L",
            tool="get_financial_report",
            tool_input={"report_type": "pandl"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert result.results[1]["total"] == 1000
    assert len(result.orchestration_log) == 1
    assert result.orchestration_log[0].status == "success"
    assert executor.calls == [("get_financial_report", {"report_type": "pandl"})]


@pytest.mark.asyncio
async def test_parallel_steps_run_concurrently() -> None:
    executor = MockToolExecutor(delay_seconds=0.05)
    orchestrator = ExecutionOrchestrator(executor)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch Q1",
            tool="group_and_aggregate",
            tool_input={"period": "Q1"},
            parallel_with=[2],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
        ExecutionStep(
            step_number=2,
            description="Fetch Q4",
            tool="group_and_aggregate",
            tool_input={"period": "Q4"},
            parallel_with=[1],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    started = time.perf_counter()
    result = await orchestrator.execute(strategy, _make_context_stack())
    elapsed = time.perf_counter() - started

    assert len(result.results) == 2
    assert executor.max_concurrent == 2
    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_depends_on_enforces_execution_order() -> None:
    executor = MockToolExecutor()
    orchestrator = ExecutionOrchestrator(executor)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Resolve clients",
            tool="search_odoo",
            tool_input={"model": "res.partner"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'res.partner'}",
        ),
        ExecutionStep(
            step_number=2,
            description="Compare revenue",
            tool="compose_report",
            tool_input={"partner_id": "{{step_1.partner_id}}"},
            depends_on=[1],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )
    executor.responses[("search_odoo", 1)] = {"partner_id": 42}

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert result.results[2]["ok"] is True
    assert executor.calls[1] == ("compose_report", {"partner_id": 42})


def test_group_parallel_steps_builds_parallel_group() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    steps = [
        ExecutionStep(
            step_number=1,
            description="Q1",
            tool="group_and_aggregate",
            tool_input={},
            parallel_with=[2],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
        ExecutionStep(
            step_number=2,
            description="Q4",
            tool="group_and_aggregate",
            tool_input={},
            parallel_with=[1],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
        ExecutionStep(
            step_number=3,
            description="Compare",
            tool="compose_report",
            tool_input={},
            depends_on=[1, 2],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    ]

    groups = orchestrator._group_parallel_steps(steps)

    assert groups == [
        [
            steps[0],
            steps[1],
        ],
        [steps[2]],
    ]


def test_resolve_variables_substitutes_step_field_reference() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    resolved = orchestrator._resolve_variables(
        {"partner_id": "{{step_1.partner_id}}", "limit": 5},
        {1: {"partner_id": 99, "rows": []}},
    )

    assert resolved == {"partner_id": 99, "limit": 5}


def test_resolve_variables_raises_when_field_missing() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())

    with pytest.raises(VariableResolutionError, match="missing field 'partner_id'"):
        orchestrator._resolve_variables(
            {"partner_id": "{{step_1.partner_id}}"},
            {1: {"rows": []}},
        )


def test_resolve_variables_raises_when_step_not_completed() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())

    with pytest.raises(VariableResolutionError, match="step_2 has no result yet"):
        orchestrator._resolve_variables(
            {"partner_id": "{{step_2.partner_id}}"},
            {1: {"partner_id": 10}},
        )


@pytest.mark.asyncio
async def test_execution_result_includes_orchestration_log_entries() -> None:
    executor = MockToolExecutor({("search_odoo", 1): {"rows": [{"id": 1}, {"id": 2}]}})
    orchestrator = ExecutionOrchestrator(executor)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Search",
            tool="search_odoo",
            tool_input={"model": "project.project"},
            fallback_if_fails="use_tool:search_odoo:{'model': 'project.project'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert len(result.orchestration_log) == 1
    entry = result.orchestration_log[0]
    assert entry.step_number == 1
    assert entry.tool == "search_odoo"
    assert entry.status == "success"
    assert entry.duration_ms >= 0
    assert entry.error is None


@pytest.mark.asyncio
async def test_parallel_step_failure_records_step_failure_when_fallback_also_fails() -> None:
    executor = MockToolExecutor(fail_tools={"group_and_aggregate", "search_odoo"})
    orchestrator = ExecutionOrchestrator(executor, retry_delay_seconds=0)
    strategy = _strategy(
        ExecutionStep(
            step_number=1,
            description="Fetch Q1",
            tool="group_and_aggregate",
            tool_input={"period": "Q1"},
            parallel_with=[2],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
        ExecutionStep(
            step_number=2,
            description="Fetch Q4",
            tool="compose_report",
            tool_input={"report_type": "comparison"},
            parallel_with=[1],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    )

    result = await orchestrator.execute(strategy, _make_context_stack())

    assert 1 not in result.results
    assert 2 in result.results
    assert len(result.failures) == 1
    assert result.failures[0].step.step_number == 1
    assert any(entry.status == "failed" for entry in result.orchestration_log)


def test_group_parallel_steps_raises_on_unsatisfiable_dependencies() -> None:
    orchestrator = ExecutionOrchestrator(MockToolExecutor())
    steps = [
        ExecutionStep(
            step_number=2,
            description="Needs missing step",
            tool="compose_report",
            tool_input={},
            depends_on=[99],
            fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
        ),
    ]

    with pytest.raises(OrchestrationException, match="unsatisfiable"):
        orchestrator._group_parallel_steps(steps)

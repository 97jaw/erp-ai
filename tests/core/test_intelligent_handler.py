"""Tests for gateway.intelligent_handler orchestration integration."""

from __future__ import annotations

from typing import Any

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.intent_analyzer import Intent
from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_execution_orchestrator import MockToolExecutor


class FixedIntentAnalyzer:
    """Return a predetermined intent without calling Claude."""

    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    async def analyze(self, query: str, context: Any) -> Intent:
        return self.intent


def _compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        estimated_complexity="complex",
        expected_output="chart",
    )


def _super_admin() -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )


def _aggregate_rows(client: str, amount: float) -> dict[str, Any]:
    return {
        "partner_id": [1, client],
        "amount_total:sum": amount,
    }


@pytest.mark.asyncio
async def test_handle_returns_orchestration_log() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.orchestration_log
    assert response.strategy_step_count == 2


@pytest.mark.asyncio
async def test_handle_runs_parallel_period_fetches() -> None:
    executor = MockToolExecutor(
        delay_seconds=0.05,
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert executor.max_concurrent == 2
    assert len(response.tools_called) == 2


@pytest.mark.asyncio
async def test_handle_synthesizes_comparison_table_visualization() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.visualization is not None
    assert response.visualization["visual_type"] in {"DATA_TABLE", "BAR_CHART"}
    assert "Client A" in str(response.visualization["data"]["rows"])


@pytest.mark.asyncio
async def test_handle_out_of_scope_returns_honest_text() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my payslip",
        out_of_scope=True,
        out_of_scope_reason="hr.payslips is unavailable. Use the HR portal directly at hr.elrace.com",
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(intent))
    response = await handler.handle(
        "what is my payslip",
        _super_admin(),
        adapter=object(),
    )

    assert response.failure_mode == "tool_not_available"
    assert "payslip" in response.text.lower() or "payroll" in response.text.lower()
    assert "hr.elrace.com" in response.text.lower() or "hr portal" in response.text.lower()
    assert "q3 2026" in response.text.lower()
    assert "database" not in response.text.lower()
    assert "try again" not in response.text.lower()
    assert response.strategy_step_count == 0
    assert response.orchestration_log == []


@pytest.mark.asyncio
async def test_handle_records_execution_duration() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.execution_duration_ms >= 0


@pytest.mark.asyncio
async def test_handle_populates_tools_called() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.tools_called.count("group_and_aggregate") == 2


@pytest.mark.asyncio
async def test_handle_attaches_execution_result() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(_compare_intent()))
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        _super_admin(),
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.execution_result is not None
    assert len(response.execution_result.results) == 2


def test_result_synthesizer_builds_change_column() -> None:
    from gateway.core.execution_orchestrator import ExecutionResult, VerificationResult
    from gateway.core.result_synthesizer import ResultSynthesizer

    execution = ExecutionResult(
        results={
            1: {"rows": [_aggregate_rows("Client A", 1000)]},
            2: {"rows": [_aggregate_rows("Client A", 800)]},
        },
        failures=[],
        verification=VerificationResult(passed=True),
        strategy_used=build_revenue_comparison_strategy(),
    )
    synthesized = ResultSynthesizer().synthesize(execution, _compare_intent())

    assert synthesized.visualization is not None
    rows = synthesized.visualization["data"]["rows"]
    assert rows[0][3] == -200.0

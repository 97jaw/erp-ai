"""Tests for gateway.core.execution_orchestrator data models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.core.entity_resolver import StepFailure
from gateway.core.execution_orchestrator import (
    ORCHESTRATION_STEP_STATUSES,
    ExecutionResult,
    OrchestrationLogEntry,
    VariableResolutionError,
    VerificationCheck,
    VerificationResult,
)
from gateway.core.strategy_planner import ExecutionStep, Strategy


def _sample_strategy() -> Strategy:
    step = ExecutionStep(
        step_number=1,
        description="Fetch Q1 revenue",
        tool="group_and_aggregate",
        tool_input={"model": "account.move"},
        fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
    )
    return Strategy(
        steps=[step],
        synthesis_approach="Compare revenue across periods",
        quality_checks=["Both periods return data"],
        estimated_duration_ms=5000,
    )


def test_orchestration_log_entry_instantiates_with_all_fields() -> None:
    timestamp = datetime(2026, 6, 6, 10, 30, tzinfo=timezone.utc)
    entry = OrchestrationLogEntry(
        step_number=1,
        tool="group_and_aggregate",
        status="success",
        duration_ms=842,
        input_summary="model=account.move, groupby=partner_id",
        output_summary="12 rows",
        error=None,
        timestamp=timestamp,
    )

    assert entry.step_number == 1
    assert entry.tool == "group_and_aggregate"
    assert entry.status == "success"
    assert entry.duration_ms == 842
    assert entry.input_summary.startswith("model=account.move")
    assert entry.output_summary == "12 rows"
    assert entry.error is None
    assert entry.timestamp == timestamp


def test_execution_result_instantiates_correctly() -> None:
    strategy = _sample_strategy()
    log_entry = OrchestrationLogEntry(
        step_number=1,
        tool="group_and_aggregate",
        status="success",
        duration_ms=500,
        input_summary="Q1 revenue",
        output_summary="10 clients",
        error=None,
        timestamp=datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc),
    )
    verification = VerificationResult(
        passed=True,
        checks=[VerificationCheck(check="Both periods return data", passed=True)],
    )
    result = ExecutionResult(
        results={1: {"rows": [{"partner_id": 10, "revenue": 1000}]}},
        failures=[],
        verification=verification,
        strategy_used=strategy,
        orchestration_log=[log_entry],
    )

    assert 1 in result.results
    assert result.failures == []
    assert result.verification.passed is True
    assert result.strategy_used is strategy
    assert len(result.orchestration_log) == 1


def test_verification_result_passed_and_failed_checks() -> None:
    passed = VerificationResult(
        passed=True,
        checks=[VerificationCheck(check="Revenue non-zero", passed=True)],
    )
    failed = VerificationResult(
        passed=False,
        checks=[
            VerificationCheck(
                check="Top 5 clients identified",
                passed=False,
                message="Only 2 clients returned",
            ),
        ],
    )

    assert passed.passed is True
    assert all(check.passed for check in passed.checks)
    assert failed.passed is False
    assert failed.checks[0].message == "Only 2 clients returned"


def test_orchestration_step_statuses_are_the_correct_strings() -> None:
    assert ORCHESTRATION_STEP_STATUSES == (
        "pending",
        "running",
        "success",
        "failed",
        "fallback",
    )


def test_variable_resolution_error_is_exception_subclass() -> None:
    with pytest.raises(VariableResolutionError, match="missing field"):
        raise VariableResolutionError("missing field revenue in step_2")


def test_execution_result_to_dict_serializes_for_logging() -> None:
    strategy = _sample_strategy()
    result = ExecutionResult(
        results={1: {"total": 5000}},
        failures=[],
        verification=VerificationResult(passed=True),
        strategy_used=strategy,
        orchestration_log=[
            OrchestrationLogEntry(
                step_number=1,
                tool="group_and_aggregate",
                status="success",
                duration_ms=120,
                input_summary="Q1",
                output_summary="ok",
                error=None,
                timestamp=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
            ),
        ],
    )

    payload = result.to_dict()

    assert payload["results"] == {1: {"total": 5000}}
    assert payload["verification"]["passed"] is True
    assert payload["strategy_used"]["estimated_duration_ms"] == 5000
    assert payload["orchestration_log"][0]["status"] == "success"
    assert payload["orchestration_log"][0]["timestamp"].endswith("+00:00")


def test_orchestration_log_entry_allows_error_on_failed_step() -> None:
    entry = OrchestrationLogEntry(
        step_number=2,
        tool="group_and_aggregate",
        status="failed",
        duration_ms=300,
        input_summary="Q4 revenue",
        output_summary="",
        error="Odoo timeout",
        timestamp=datetime(2026, 6, 6, 10, 5, tzinfo=timezone.utc),
    )

    assert entry.status == "failed"
    assert entry.error == "Odoo timeout"
    assert entry.output_summary == ""


def test_execution_result_with_failures_records_step_failure() -> None:
    step = ExecutionStep(
        step_number=2,
        description="Fetch Q4 revenue",
        tool="group_and_aggregate",
        tool_input={"model": "account.move"},
        fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
    )
    failure = StepFailure(step=step, error="Connection reset")
    result = ExecutionResult(
        results={1: {"rows": []}},
        failures=[failure],
        verification=VerificationResult(passed=False),
        strategy_used=_sample_strategy(),
    )

    assert len(result.failures) == 1
    assert result.failures[0].step.step_number == 2
    assert str(result.failures[0].error) == "Connection reset"
    assert result.orchestration_log == []

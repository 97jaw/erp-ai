"""Tests for gateway.core.quality_gate."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.intent_analyzer import Ambiguity, Intent
from gateway.core.quality_gate import (
    MAX_QUALITY_RETRIES,
    MIN_PASS_RATE,
    QUALITY_CHECKS,
    CheckResult,
    QualityGate,
    QualityResponse,
    RetryHandler,
)
from tests.core.test_context_stack import _make_context_stack


def _compare_intent(**overrides: Any) -> Intent:
    defaults = {
        "primary_action": "compare",
        "subject_area": "financial",
        "specific_intent": "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        "expected_output": "chart",
        "estimated_complexity": "complex",
    }
    defaults.update(overrides)
    return Intent(**defaults)


def _good_response(**overrides: Any) -> QualityResponse:
    defaults = {
        "text": (
            "National Guard generated AED 1,200,000 in Q1 2026 revenue based on "
            "posted customer invoices."
        ),
        "visualization": {
            "visual_type": "DATA_TABLE",
            "data": {
                "headers": [
                    "Client",
                    "Period 1 Revenue (AED)",
                    "Period 2 Revenue (AED)",
                    "Change (AED)",
                ],
                "rows": [
                    ["National Guard", 1_200_000.0, 980_000.0, -220_000.0],
                ],
            },
        },
        "suggestions": [
            "Compare National Guard project expenses for the same period.",
        ],
        "tool_results": [
            {
                "groups": [
                    {
                        "partner_id": [1, "National Guard"],
                        "amount_total:sum": 1_200_000.0,
                    },
                    {
                        "partner_id": [1, "National Guard"],
                        "amount_total:sum": 980_000.0,
                    },
                ],
            },
        ],
    }
    defaults.update(overrides)
    return QualityResponse(**defaults)


@pytest.mark.asyncio
async def test_raw_amount_total_sum_fails_no_raw_syntax() -> None:
    gate = QualityGate()
    response = _good_response(
        text="Top client amount_total:sum was AED 1,200,000 in Q1 2026.",
    )
    review = await gate.review(response, _compare_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "no_raw_syntax")
    assert check.passed is False
    assert check.issue is not None
    assert "amount_total:sum" in check.issue


@pytest.mark.asyncio
async def test_m2o_tuple_fails_no_raw_syntax() -> None:
    gate = QualityGate()
    response = _good_response(
        text="Top client [54, 'Partner Name'] generated AED 1,200,000 in Q1 2026.",
    )
    review = await gate.review(response, _compare_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "no_raw_syntax")
    assert check.passed is False
    assert check.issue is not None


@pytest.mark.asyncio
async def test_invented_numbers_fail_no_fabrication() -> None:
    gate = QualityGate()
    response = _good_response(
        text="National Guard generated AED 5,000,000 in Q1 2026 revenue.",
    )
    review = await gate.review(response, _compare_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "no_fabrication")
    assert check.passed is False
    assert check.issue is not None
    assert "not present in tool results" in check.issue


@pytest.mark.asyncio
async def test_consistent_data_passes_data_consistency() -> None:
    gate = QualityGate()
    review = await gate.review(_good_response(), _compare_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "data_consistency")
    assert check.passed is True


@pytest.mark.asyncio
async def test_inconsistent_totals_fail_data_consistency() -> None:
    gate = QualityGate()
    response = _good_response(
        visualization={
            "visual_type": "DATA_TABLE",
            "data": {
                "headers": [
                    "Client",
                    "Period 1 Revenue (AED)",
                    "Period 2 Revenue (AED)",
                    "Change (AED)",
                ],
                "rows": [
                    ["National Guard", 1_200_000.0, 980_000.0, 500_000.0],
                ],
            },
        },
    )
    review = await gate.review(response, _compare_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "data_consistency")
    assert check.passed is False
    assert check.issue is not None
    assert "does not match" in check.issue


def test_pass_rate_eight_of_nine_passes_overall() -> None:
    checks = [
        CheckResult(name=name, passed=True, issue=None)
        for name in QUALITY_CHECKS[:-1]
    ]
    checks.append(
        CheckResult(
            name=QUALITY_CHECKS[-1],
            passed=False,
            issue="Suggestions are too generic — make them specific and actionable",
        ),
    )
    review = QualityGate._finalize_review(checks)
    assert review.pass_rate == pytest.approx(8 / 9)
    assert review.passed is True
    assert review.pass_rate >= MIN_PASS_RATE


def test_pass_rate_seven_of_nine_fails_overall() -> None:
    checks = [
        CheckResult(name=name, passed=True, issue=None)
        for name in QUALITY_CHECKS[:-2]
    ]
    checks.extend([
        CheckResult(
            name=QUALITY_CHECKS[-2],
            passed=False,
            issue="Provide at least one specific follow-up suggestion",
        ),
        CheckResult(
            name=QUALITY_CHECKS[-1],
            passed=False,
            issue="Response exposes technical jargon matching 'partner_id'",
        ),
    ])
    review = QualityGate._finalize_review(checks)
    assert review.pass_rate == pytest.approx(7 / 9)
    assert review.passed is False


@pytest.mark.asyncio
async def test_failed_check_includes_descriptive_issue() -> None:
    gate = QualityGate()
    response = _good_response(suggestions=[])
    review = await gate.review(response, _compare_intent(), _make_context_stack())
    failed = [check for check in review.checks if not check.passed]
    assert failed
    assert all(check.issue and len(check.issue) > 10 for check in failed)


@pytest.mark.asyncio
async def test_retry_triggered_when_pass_rate_below_threshold() -> None:
    retry_calls: list[QualityResponse] = []

    async def reviser(
        response: QualityResponse,
        review: Any,
        intent: Intent,
        context: Any,
    ) -> QualityResponse:
        retry_calls.append(response)
        return _good_response()

    gate = QualityGate(retry_handler=RetryHandler(reviser=reviser))
    failing = _good_response(suggestions=[])

    final_response, final_review, retries = await gate.ensure_quality(
        failing,
        _compare_intent(),
        _make_context_stack(),
    )

    assert retry_calls
    assert final_review.passed is True
    assert final_response.text.startswith("National Guard generated")


@pytest.mark.asyncio
async def test_after_two_retries_response_returned_even_if_still_failing() -> None:
    retry_count = 0

    async def reviser(
        response: QualityResponse,
        review: Any,
        intent: Intent,
        context: Any,
    ) -> QualityResponse:
        nonlocal retry_count
        retry_count += 1
        return _good_response(
            text=f"{response.text} retry-{retry_count}",
            suggestions=[],
        )

    gate = QualityGate(retry_handler=RetryHandler(reviser=reviser))
    failing = _good_response(suggestions=[])

    final_response, final_review, retries = await gate.ensure_quality(
        failing,
        _compare_intent(),
        _make_context_stack(),
    )

    assert retry_count == MAX_QUALITY_RETRIES
    assert final_review.passed is False
    assert final_response.text.endswith(f"retry-{MAX_QUALITY_RETRIES}")


@pytest.mark.asyncio
async def test_retry_handler_produces_different_response() -> None:
    original = _good_response(suggestions=[])
    revised_text = "Different revised narrative with AED 1,200,000 backed by invoices."

    async def reviser(
        response: QualityResponse,
        review: Any,
        intent: Intent,
        context: Any,
    ) -> QualityResponse:
        return _good_response(text=revised_text)

    handler = RetryHandler(reviser=reviser)
    review = QualityGate()._finalize_review([
        CheckResult(
            name="actionable_suggestions",
            passed=False,
            issue="Provide at least one specific follow-up suggestion",
        ),
    ])
    revised = await handler.retry_with_feedback(
        original,
        review,
        _compare_intent(),
        _make_context_stack(),
    )

    assert revised.text != original.text
    assert revised.text == revised_text


@pytest.mark.asyncio
async def test_quality_review_contains_all_checks_run() -> None:
    gate = QualityGate()
    review = await gate.review(_good_response(), _compare_intent(), _make_context_stack())
    assert len(review.checks) == len(QUALITY_CHECKS)
    assert [check.name for check in review.checks] == list(QUALITY_CHECKS)


def _expense_intent(**overrides: Any) -> Intent:
    defaults = {
        "primary_action": "fetch_data",
        "subject_area": "project",
        "specific_intent": "Villa No. 48 expense this year",
        "entities": [],
        "expected_output": "summary",
    }
    defaults.update(overrides)
    return Intent(**defaults)


def _zero_expense_response(**overrides: Any) -> QualityResponse:
    defaults = {
        "text": "Villa 48: total spend AED 0 of W.O AED 0. Status: on track.",
        "visualization": {
            "visual_type": "PROJECT_EXPENSE_SUMMARY",
            "project_name": "Villa No. 48",
            "kpis": {
                "wo_amount": {"value": 0},
                "total_expenses": {"value": 0},
                "spend_pct": {
                    "value": 0,
                    "trend": {"direction": "neutral", "context": "On track"},
                },
            },
        },
        "suggestions": ["Show me the cost breakdown for Villa 48."],
        "tool_results": [
            {
                "status": "success",
                "_source": "project_expense_summary_mobile",
                "project_name": "Villa No. 48",
                "wo_amount": 0,
                "total_expenses": 0,
            },
        ],
    }
    defaults.update(overrides)
    return QualityResponse(**defaults)


@pytest.mark.asyncio
async def test_zero_values_with_success_fails_quality() -> None:
    gate = QualityGate()
    review = await gate.review(
        _zero_expense_response(),
        _expense_intent(),
        _make_context_stack(),
    )

    assert not review.passed
    failed = [check for check in review.checks if not check.passed]
    assert any(check.name == "not_all_zero" for check in failed)


@pytest.mark.asyncio
async def test_zero_values_without_success_still_fails() -> None:
    gate = QualityGate()
    response = _zero_expense_response(
        text="Villa 48 expenses: AED 0 spent of AED 0 budget.",
        visualization={"wo_amount": 0, "total_expenses": 0},
    )
    review = await gate.review(response, _expense_intent(), _make_context_stack())

    check = next(item for item in review.checks if item.name == "not_all_zero")
    assert check.passed is False


@pytest.mark.asyncio
async def test_real_zero_spent_with_real_budget_passes() -> None:
    gate = QualityGate()
    response = _zero_expense_response(
        text="Villa 48: spent AED 0 of AED 100,000 W.O budget. Project not yet started.",
        visualization={
            "visual_type": "PROJECT_EXPENSE_SUMMARY",
            "project_name": "Villa No. 48",
            "kpis": {
                "wo_amount": {"value": 100_000},
                "total_expenses": {"value": 0},
                "variance": {"value": 100_000},
                "spend_pct": {"value": 0},
            },
        },
    )
    review = await gate.review(response, _expense_intent(), _make_context_stack())
    check = next(item for item in review.checks if item.name == "not_all_zero")
    assert check.passed is True


@pytest.mark.asyncio
async def test_quality_gate_retries_on_zero_data() -> None:
    from gateway.core.quality_pipeline import QualityResponseReviser

    gate = QualityGate(retry_handler=RetryHandler(reviser=QualityResponseReviser()))
    final_response, final_review, retries = await gate.ensure_quality(
        _zero_expense_response(),
        _expense_intent(),
        _make_context_stack(),
    )

    assert retries >= 1
    assert "no expense data recorded" in final_response.text.lower()
    assert "on track" not in final_response.text.lower()
    not_all_zero = next(
        check for check in final_review.checks if check.name == "not_all_zero"
    )
    assert not_all_zero.passed is True


def _contradiction_expense_response(**overrides: Any) -> QualityResponse:
    defaults = {
        "text": "Villa 34: total spend is AED 12,000 (2% of W.O AED 0). Status: on track.",
        "visualization": {
            "visual_type": "PROJECT_EXPENSE_SUMMARY",
            "project_name": "Villa Maintenance No. 34",
            "kpis": {
                "wo_amount": {"value": 0},
                "total_expenses": {"value": 12000},
                "spend_pct": {"value": 2},
            },
        },
        "suggestions": [],
        "tool_results": [],
    }
    defaults.update(overrides)
    return QualityResponse(**defaults)


@pytest.mark.asyncio
async def test_quality_catches_pct_of_zero() -> None:
    gate = QualityGate()
    review = await gate.review(
        _contradiction_expense_response(),
        _expense_intent(),
        _make_context_stack(),
    )

    check = next(item for item in review.checks if item.name == "no_contradictions")
    assert check.passed is False
    assert check.issue is not None
    assert "W.O is 0" in check.issue


@pytest.mark.asyncio
async def test_quality_catches_on_track_over_budget() -> None:
    gate = QualityGate()
    response = _contradiction_expense_response(
        text="Villa 34: total spend is AED 15,000. Status: on track.",
        visualization={
            "visual_type": "PROJECT_EXPENSE_SUMMARY",
            "project_name": "Villa Maintenance No. 34",
            "kpis": {
                "wo_amount": {"value": 10000},
                "total_expenses": {"value": 15000},
                "spend_pct": {"value": 150},
            },
        },
    )
    review = await gate.review(response, _expense_intent(), _make_context_stack())

    check = next(item for item in review.checks if item.name == "no_contradictions")
    assert check.passed is False
    assert check.issue is not None
    assert "on track" in check.issue.lower()

"""Tests for gateway.core.failure_handler — Phase 6."""

from __future__ import annotations

import pytest

from gateway.core.failure_handler import (
    FABRICATION_PHRASES,
    Failure,
    FailureMode,
    HonestFailureResponder,
    contains_fabricated_excuse,
)
from gateway.core.intent_analyzer import Intent
from tests.core.test_context_stack import _make_context_stack


def _responder() -> HonestFailureResponder:
    return HonestFailureResponder()


def _payslip_intent() -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my payslip",
        out_of_scope=True,
        out_of_scope_reason="hr.payslips is unavailable. Use the HR portal directly at hr.elrace.com",
    )


@pytest.mark.parametrize("mode", list(FailureMode))
def test_all_failure_modes_render_non_empty_text(mode: FailureMode) -> None:
    context = _make_context_stack()
    failure = Failure(
        mode=mode,
        user_message="sample query",
        capability_code="hr.payslips" if mode == FailureMode.TOOL_NOT_AVAILABLE else None,
        details={
            "query_label": "sample query",
            "strategies_tried": ["group_and_aggregate"],
            "reason": "Not supported in this assistant.",
            "data_type": "payroll data",
            "required_permission": "hr.payroll.read",
            "tool_name": "group_and_aggregate",
            "error_summary": "Access denied",
            "match_count": 2,
            "matches": [
                {"name": "National Guard", "wo_ref_no": "WO-100"},
                {"name": "National Guard Phase 2", "client": "NG"},
            ],
            "period_label": "last fortnight",
            "detail": "Multiple projects share that name.",
            "department": "Finance",
        },
    )
    response = _responder().respond(failure, context)
    assert response.text.strip()
    assert response.failure_mode == mode
    assert "{" not in response.text
    assert "}" not in response.text


def test_payslip_intent_maps_to_out_of_scope_when_capability_live() -> None:
    """Stale LLM out_of_scope for payslips; capability is live so not tool_not_available."""
    failure = HonestFailureResponder.failure_from_intent(
        _payslip_intent(),
        "what is my payslip",
    )
    assert failure.mode == FailureMode.OUT_OF_SCOPE
    assert failure.capability_code is None


def test_payslip_response_is_honest_when_stale_out_of_scope() -> None:
    context = _make_context_stack()
    failure = HonestFailureResponder.failure_from_intent(
        _payslip_intent(),
        "what is my payslip",
    )
    response = _responder().respond(failure, context)
    lowered = response.text.lower()

    assert "can't help" in lowered or "outside" in lowered
    assert not contains_fabricated_excuse(response.text)


def test_out_of_scope_without_capability_code() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="general",
        specific_intent="book me a flight",
        out_of_scope=True,
        out_of_scope_reason="Travel booking is outside this assistant.",
    )
    failure = HonestFailureResponder.failure_from_intent(intent, "book me a flight")
    response = _responder().respond(failure, _make_context_stack())

    assert failure.mode == FailureMode.OUT_OF_SCOPE
    assert "can't help" in response.text.lower() or "outside" in response.text.lower()
    assert not contains_fabricated_excuse(response.text)


def test_coming_soon_capability_uses_feature_mode() -> None:
    intent = Intent(
        primary_action="forecast",
        subject_area="financial",
        specific_intent="Forecast next month's cash position",
        out_of_scope=True,
        out_of_scope_reason="Cash flow forecasting is not live yet.",
    )
    failure = HonestFailureResponder.failure_from_intent(
        intent,
        "Forecast next month's cash position",
    )
    assert failure.mode == FailureMode.FEATURE_COMING_SOON
    response = _responder().respond(failure, _make_context_stack())
    assert "forecast" in response.text.lower() or "planned" in response.text.lower()
    assert not contains_fabricated_excuse(response.text)


def test_ambiguous_reference_super_admin_is_decisive() -> None:
    context = _make_context_stack(primary_role="super_admin", level=90)
    failure = Failure(
        mode=FailureMode.AMBIGUOUS_REFERENCE,
        user_message="National Guard costs",
        details={
            "query_label": "National Guard",
            "match_count": 2,
            "matches": [
                {"name": "National Guard", "wo_ref_no": "WO-100"},
                {"name": "National Guard Phase 2", "wo_ref_no": "WO-200"},
            ],
        },
    )
    response = _responder().respond(failure, context)
    assert "National Guard" in response.text
    assert "unless you say otherwise" in response.text.lower()


def test_entity_resolution_stage_maps_to_tool_error_not_data_ambiguous() -> None:
    failure = HonestFailureResponder.failure_from_stage(
        "entity_resolution",
        ValueError("adapter timeout"),
        "show me Zayidia Boys School costs",
    )
    assert failure is not None
    assert failure.mode == FailureMode.TOOL_ERROR
    assert failure.mode != FailureMode.DATA_AMBIGUOUS


def test_entity_not_found_helper_uses_no_data_found() -> None:
    failure = HonestFailureResponder.failure_from_entity_not_found(
        "show me Zayidia Boys School costs",
        query_label="Zayidia Boys School",
    )
    assert failure.mode == FailureMode.NO_DATA_FOUND


def test_entity_not_found_template_uses_project_copy() -> None:
    failure = HonestFailureResponder.failure_from_entity_not_found(
        "show me Zayidia Boys School costs",
        query_label="Zayidia Boys School",
    )
    response = _responder().respond(failure, _make_context_stack())
    assert "couldn't find a project matching" in response.text.lower()
    assert "work order" in response.text.lower()
    assert "double-count" not in response.text.lower()


def test_entity_resolution_needs_confirm_is_not_a_failure() -> None:
    failure = HonestFailureResponder.failure_from_entity_resolution(
        "needs_confirm",
        "show me Zayidia Boys School costs",
    )
    assert failure is None


def test_no_data_failure_from_intent_helper() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show revenue by client last quarter",
    )
    failure = HonestFailureResponder.failure_from_no_data(
        intent,
        "Show revenue by client last quarter",
        strategies_tried=["posted invoices", "wider filters"],
    )
    response = _responder().respond(failure, _make_context_stack())
    assert failure.mode == FailureMode.NO_DATA_FOUND
    assert response.text.startswith("No data found for")
    assert "posted invoices" in response.text.lower()
    assert not contains_fabricated_excuse(response.text)


def test_contains_fabricated_excuse_detects_forbidden_phrases() -> None:
    for phrase in FABRICATION_PHRASES[:3]:
        assert contains_fabricated_excuse(f"Sorry, we hit a {phrase}.")

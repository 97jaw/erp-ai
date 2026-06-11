"""Tests for gateway.core.quality_pipeline."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import Intent
from gateway.core.quality_pipeline import (
    NO_DATA_PREFIX,
    _BREAKDOWN_EMPTY_WITH_SUMMARY_SUFFIX,
    build_quality_response,
    has_meaningful_tool_data,
    no_data_message,
    strip_raw_syntax,
)
from tests.core.test_context_stack import _make_context_stack


def _intent(
    *,
    subject_area: str = "financial",
    specific_intent: str = "Show revenue by client last quarter",
) -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area=subject_area,
        specific_intent=specific_intent,
        expected_output="table",
    )


def test_has_meaningful_tool_data_requires_non_zero_values() -> None:
    assert has_meaningful_tool_data([
        {"groups": [{"partner_id": [1, "Client A"], "amount_total:sum": 0.0}]},
    ]) is False
    assert has_meaningful_tool_data([
        {"groups": [{"partner_id": [1, "Client A"], "amount_total:sum": 1500.0}]},
    ]) is True


def test_no_data_message_uses_required_prefix() -> None:
    message = no_data_message(_intent())
    assert message.startswith(NO_DATA_PREFIX)


def test_no_data_message_for_project_expense_omits_invoice_filters() -> None:
    message = no_data_message(
        _intent(subject_area="project", specific_intent="get_project_expense_breakdown"),
        tool_names=["get_project_expense_breakdown"],
    )
    assert "posted invoice filters" not in message
    assert "project expense breakdown" in message or "expense summary" in message


def test_no_data_message_for_financial_tool_uses_report_wording() -> None:
    message = no_data_message(
        _intent(),
        tool_names=["get_financial_report"],
    )
    assert "posted journal entries" in message
    assert "group_and_aggregate" not in message


def test_breakdown_empty_with_prior_summary_suggests_trade_categories() -> None:
    context = _make_context_stack()
    context.working_memory.session_facts["last_expense_summary_project_id"] = 15157
    context.working_memory.session_facts["project_name"] = "Villa Maintenance No. 34 (WO: Pending)"

    message = no_data_message(
        _intent(subject_area="project", specific_intent="get_project_expense_breakdown"),
        tool_names=["get_project_expense_breakdown"],
        context=context,
        tool_results=[
            {
                "status": "success",
                "_source": "project_expense_breakdown_mobile",
                "project_id": 15157,
                "project_name": "Villa Maintenance No. 34 (WO: Pending)",
                "groups": [],
                "grand_total": 0,
            },
        ],
    )

    assert "posted invoice filters" not in message
    assert "Villa Maintenance No. 34" in message
    assert "GL breakdown has no data" in message
    assert _BREAKDOWN_EMPTY_WITH_SUMMARY_SUFFIX in message


def test_strip_raw_syntax_removes_odoo_artifacts() -> None:
    cleaned = strip_raw_syntax(
        "Top client amount_total:sum was [54, 'Partner Name'] with partner_id_count."
    )
    assert "amount_total:sum" not in cleaned
    assert "[54, 'Partner Name']" not in cleaned


@pytest.mark.asyncio
async def test_build_quality_response_honest_when_tool_data_empty() -> None:
    response = build_quality_response(
        message="Show revenue by client last quarter",
        text="National Guard generated AED 1,200,000.",
        visualization=None,
        tool_names=["group_and_aggregate"],
        tool_results=[{"groups": [{"partner_id": [1, "Client"], "amount_total:sum": 0.0}]}],
        language="en",
        intent=_intent(),
    )
    assert response.text.startswith(NO_DATA_PREFIX)
    assert response.visualization is None

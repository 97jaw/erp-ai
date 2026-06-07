"""Tests for gateway.core.quality_pipeline."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import Intent
from gateway.core.quality_pipeline import (
    NO_DATA_PREFIX,
    build_quality_response,
    has_meaningful_tool_data,
    no_data_message,
    strip_raw_syntax,
)
from tests.core.test_context_stack import _make_context_stack


def _intent() -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show revenue by client last quarter",
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

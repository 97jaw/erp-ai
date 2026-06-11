"""Tests for the conversational fixes: near-miss confirm, P&L no-data, report routing,
date-range resolution, and the Deep Think date clarification card."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.clarify import build_deep_think_date_clarification
from gateway.core.entity_gate import ConfirmedEntityRef, EntityGate
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.quality_pipeline import has_meaningful_tool_data, no_data_message
from gateway.core.strategy_planner import (
    StrategyPlanner,
    match_company_report,
    resolve_report_date_range,
)
from gateway.core.temporal_context import TemporalContext
from tests.core.test_context_stack import _make_context_stack


# ---------------------------------------------------------------------------
# Bug 1 — near-miss confirmation must be authoritative (no re-validation loop)
# ---------------------------------------------------------------------------


class _ExplodingAdapter:
    """Adapter that fails the test if any Odoo discovery is attempted."""

    def search_read(self, **kwargs):
        raise AssertionError("Odoo discovery must not run for user-confirmed entities")

    def safe_search_read(self, **kwargs):
        raise AssertionError("Odoo discovery must not run for user-confirmed entities")


@pytest.mark.asyncio
async def test_user_confirmed_near_miss_entity_skips_revalidation() -> None:
    """Picking 'Villa Maintenance No. 34' for query 'Villa maintainacne 37' must confirm,
    not loop back into the same clarification."""
    gate = EntityGate(_ExplodingAdapter())
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me expense for Villa maintainacne 37",
        entities=[EntityReference(type="project", value="Villa maintainacne 37", confidence=0.9)],
    )
    context = _make_context_stack()
    result = await gate.evaluate(
        intent,
        context,
        "show me expense for Villa maintainacne 37",
        confirmed_entities=[
            ConfirmedEntityRef(type="project", id=15157, name="Villa Maintenance No. 34"),
        ],
    )
    assert result.status == "confirmed"
    assert result.confirmed["project"]["id"] == 15157
    assert result.confirmed["project"]["name"] == "Villa Maintenance No. 34"


# ---------------------------------------------------------------------------
# Bug 2 — P&L payloads must count as meaningful data
# ---------------------------------------------------------------------------


def _pandl_payload(income: float, expense: float) -> dict:
    return {
        "report_type": "pandl",
        "report_name": "Profit & Loss",
        "report_lines": [
            {"name": "Income", "balance": -income, "debit": 0.0, "credit": income, "level": 1},
            {"name": "Expense", "balance": expense, "debit": expense, "credit": 0.0, "level": 1},
        ],
        "kpis": {
            "total_income": income,
            "total_expense": expense,
            "net_profit": income - expense,
            "margin": 12.5 if income else 0.0,
        },
    }


def test_pandl_report_counts_as_meaningful_data() -> None:
    assert has_meaningful_tool_data([_pandl_payload(1_500_000.0, 900_000.0)]) is True


def test_pandl_report_with_zero_values_is_not_meaningful() -> None:
    payload = _pandl_payload(0.0, 0.0)
    payload["kpis"]["margin"] = 0.0
    assert has_meaningful_tool_data([payload]) is False


def test_no_data_message_blank_specific_intent_falls_back_to_user_message() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="",
    )
    message = no_data_message(intent, user_message="Show me the P&L for the last 3 months")
    assert "for ." not in message
    assert "Show me the P&L for the last 3 months" in message


def test_no_data_message_financial_omits_spelling_hint_and_raw_syntax() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="P&L for the last 3 months",
    )
    message = no_data_message(intent, user_message="Show me the P&L for the last 3 months")
    assert "spelling of the client or project name" not in message
    assert "data search" not in message
    assert "group_and_aggregate" not in message


# ---------------------------------------------------------------------------
# Report routing guardrail + date range resolution
# ---------------------------------------------------------------------------


def test_match_company_report_detects_report_names() -> None:
    assert match_company_report("Show me the P&L for the last 3 months") == (
        "get_financial_report",
        "pandl",
    )
    assert match_company_report("profit and loss statement") == ("get_financial_report", "pandl")
    assert match_company_report("balance sheet for this year") == (
        "get_financial_report",
        "balance_sheet",
    )
    assert match_company_report("trial balance ytd") == ("get_trial_balance", None)
    assert match_company_report("revenue by client last quarter") is None
    assert match_company_report("show me expenses for Villa 34") is None


def _temporal() -> TemporalContext:
    return TemporalContext.build(datetime(2026, 6, 6, tzinfo=timezone.utc))


def test_resolve_report_date_range_periods() -> None:
    temporal = _temporal()
    assert resolve_report_date_range("P&L from 2026-01-01 to 2026-03-31", temporal) == (
        "2026-01-01",
        "2026-03-31",
    )
    assert resolve_report_date_range("P&L for this year", temporal) == temporal.ytd
    assert resolve_report_date_range("P&L for last month", temporal) == temporal.last_month
    assert resolve_report_date_range("P&L for last quarter", temporal) == temporal.last_quarter
    assert resolve_report_date_range("P&L for the last 3 months", temporal) == temporal.last_3_months
    # No period named — product default.
    assert resolve_report_date_range("Show me the P&L", temporal) == temporal.last_3_months


def test_resolve_report_date_range_last_n_months() -> None:
    temporal = _temporal()
    date_from, date_to = resolve_report_date_range("P&L for the last 6 months", temporal)
    assert date_to == temporal.today.isoformat()
    assert date_from < temporal.last_3_months[0]


class _NoopClient:
    async def complete_json(self, *args, **kwargs):
        raise AssertionError("Claude must not be called for guarded report routing")


@pytest.mark.asyncio
async def test_misclassified_pandl_query_is_forced_to_financial_report_tool() -> None:
    """Even when intent analysis misroutes a P&L query toward entity search,
    the planner must route it to get_financial_report."""
    planner = StrategyPlanner(client=_NoopClient())
    intent = Intent(
        primary_action="search_entity",
        subject_area="general",
        specific_intent="find data",
        estimated_complexity="simple",
    )
    context = _make_context_stack()  # conversation message: "Show P&L for last quarter"
    strategy = await planner.plan(intent, context)
    assert len(strategy.steps) == 1
    step = strategy.steps[0]
    assert step.tool == "get_financial_report"
    assert step.tool_input["report_type"] == "pandl"
    assert (step.tool_input["date_from"], step.tool_input["date_to"]) == tuple(
        context.temporal_context.last_quarter,
    )


@pytest.mark.asyncio
async def test_simple_pandl_intent_respects_named_period() -> None:
    from dataclasses import replace as dc_replace

    planner = StrategyPlanner(client=_NoopClient())
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show P&L for this year",
        estimated_complexity="simple",
    )
    context = _make_context_stack()
    context.conversation = dc_replace(context.conversation, message="Show P&L for this year")
    strategy = await planner.plan(intent, context)
    step = strategy.steps[0]
    assert step.tool == "get_financial_report"
    assert (step.tool_input["date_from"], step.tool_input["date_to"]) == tuple(
        context.temporal_context.ytd,
    )


# ---------------------------------------------------------------------------
# Deep Think date clarification card (normal mode, report queries)
# ---------------------------------------------------------------------------


def test_deep_think_date_card_flags_every_option() -> None:
    temporal = _temporal()
    card = build_deep_think_date_clarification(
        "Show me the P&L for the last 3 months",
        temporal,
        "en",
    )
    assert card["resume_deep_think"] is True
    assert card["reason"] == "date_range_deep_think"
    assert all(option.get("deep_think") for option in card["options"])
    assert card["skip_option"]["deep_think"] is True


def test_deep_think_date_card_marks_detected_period_default() -> None:
    temporal = _temporal()
    card = build_deep_think_date_clarification(
        "Show me the P&L for the last 3 months",
        temporal,
        "en",
    )
    defaults = [option for option in card["options"] if option.get("is_default")]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "last_3m"
    expected_suffix = f" from {temporal.last_3_months[0]} to {temporal.last_3_months[1]}"
    assert defaults[0]["query_suffix"] == expected_suffix
    assert card["skip_option"]["query_suffix"] == expected_suffix


def test_deep_think_date_card_uses_explicit_dates_so_phrases_cannot_conflict() -> None:
    temporal = _temporal()
    card = build_deep_think_date_clarification("Show me the P&L for this year", temporal, "en")
    ytd_option = next(option for option in card["options"] if option["id"] == "ytd")
    assert ytd_option["is_default"] is True
    # Picking a different preset must still win over "this year" in the message.
    last_month = next(option for option in card["options"] if option["id"] == "last_month")
    enriched = f"Show me the P&L for this year{last_month['query_suffix']}"
    assert resolve_report_date_range(enriched, temporal) == temporal.last_month


def test_deep_think_date_card_includes_custom_picker() -> None:
    card = build_deep_think_date_clarification("balance sheet", _temporal(), "en")
    custom = next(option for option in card["options"] if option["id"] == "custom")
    assert custom["action"] == "open_date_picker"
    assert custom["deep_think"] is True

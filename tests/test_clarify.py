from __future__ import annotations

from gateway.clarify import (
    build_date_range_clarification,
    enrich_query_with_clarification,
    parse_clarify_block,
    should_offer_date_clarification,
    strip_clarify_markup,
)


def test_should_offer_date_clarification_for_pnl_without_dates() -> None:
    assert should_offer_date_clarification("show P&L") is True
    assert should_offer_date_clarification("show P&L for this month") is False
    assert should_offer_date_clarification("hello") is False


def test_should_not_offer_date_clarification_when_month_year_present() -> None:
    assert should_offer_date_clarification("jawad ur rehman, may 2026") is False
    assert should_offer_date_clarification("show payroll cost for May 2026") is False


def test_should_not_offer_date_clarification_for_named_project_expense() -> None:
    assert should_offer_date_clarification("Villa Maintenance No. 34 expense") is False
    assert should_offer_date_clarification("show me Zayidia Boys School costs") is False


def test_parse_clarify_block() -> None:
    text = '<clarify>{"reason":"date_range_missing","question":"Which period?"}</clarify>'
    payload = parse_clarify_block(text)
    assert payload is not None
    assert payload["reason"] == "date_range_missing"


def test_strip_clarify_markup() -> None:
    text = "Hello<clarify>{\"question\":\"Q?\"}</clarify> world"
    assert strip_clarify_markup(text) == "Hello world"


def test_enrich_query_with_clarification() -> None:
    option = {"query_suffix": " for the last 3 months"}
    assert enrich_query_with_clarification("P&L", option) == "P&L for the last 3 months"


def test_build_date_range_clarification_has_options() -> None:
    payload = build_date_range_clarification("en")
    assert len(payload["options"]) >= 4
    assert payload["skip_option"]["query_suffix"]

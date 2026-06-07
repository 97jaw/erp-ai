from __future__ import annotations

from datetime import date, timedelta

from gateway.date_utils import DEFAULT_RANGE_DAYS, enforce_date_range, get_default_date_range


def test_get_default_date_range_span() -> None:
    date_from, date_to = get_default_date_range()
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    assert (end - start).days == DEFAULT_RANGE_DAYS


def test_enforce_injects_defaults_for_financial_tool() -> None:
    out = enforce_date_range("get_financial_report", {})
    assert out["date_from"]
    assert out["date_to"]
    assert out.get("_date_was_defaulted") is True


def test_enforce_skips_non_financial_tool() -> None:
    payload = {"model": "res.partner"}
    out = enforce_date_range("search_odoo", payload)
    assert out is payload
    assert "date_from" not in out


def test_enforce_swaps_inverted_range() -> None:
    out = enforce_date_range(
        "query_accounting",
        {"date_from": "2026-05-01", "date_to": "2026-01-01"},
    )
    assert out["date_from"] == "2026-01-01"
    assert out["date_to"] == "2026-05-01"

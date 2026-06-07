"""Tests for gateway.core.business_context."""

from gateway.core.business_context import BusinessContext


def test_company_name_is_correct():
    context = BusinessContext()
    assert context.company_name == "Elrace Cos. & Gen. Cont. CO."


def test_currency_is_aed():
    context = BusinessContext()
    assert context.currency == "AED"


def test_healthy_margin_tuple_is_15_30():
    context = BusinessContext()
    assert context.business_norms["healthy_gross_margin"] == (15, 30)


def test_concerning_dso_is_90():
    context = BusinessContext()
    assert context.business_norms["concerning_dso"] == 90


def test_top_clients_includes_national_guard():
    context = BusinessContext()
    assert "National Guard" in context.top_clients


def test_summary_non_empty_and_contains_aed():
    context = BusinessContext()
    summary = context.summary()
    assert summary.strip()
    assert "AED" in summary

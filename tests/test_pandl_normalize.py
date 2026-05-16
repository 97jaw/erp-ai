from __future__ import annotations

from gateway.accounting_sql.post_process import post_process_pandl
from gateway.pandl_normalize import extract_pandl_kpis, normalize_pandl_report


def test_extract_pandl_kpis_from_level_one_sections() -> None:
    lines = [
        {"name": "Income", "balance": -1000.0, "level": 1},
        {"name": "Expenses", "balance": 400.0, "level": 1},
    ]
    kpis = extract_pandl_kpis(lines)
    assert kpis["total_income"] == 1000.0
    assert kpis["total_expense"] == 400.0
    assert kpis["net_profit"] == 600.0
    assert kpis["margin"] == 60.0


def test_post_process_pandl_sql_rows() -> None:
    rows = [
        {
            "internal_group": "income",
            "account_code": "4000",
            "account_name": "Sales",
            "debit_sum": 0.0,
            "credit_sum": 1000.0,
            "balance_sum": 1000.0,
        },
        {
            "internal_group": "expense",
            "account_code": "6000",
            "account_name": "Rent",
            "debit_sum": 300.0,
            "credit_sum": 0.0,
            "balance_sum": -300.0,
        },
    ]
    result = post_process_pandl(
        rows,
        date_from="2026-05-01",
        date_to="2026-05-16",
        company_id=1,
    )
    assert result["report_type"] == "pandl"
    assert result["kpis"]["total_income"] == 1000.0
    assert result["kpis"]["total_expense"] == 300.0
    assert result["kpis"]["net_profit"] == 700.0


def test_normalize_pandl_report_shape() -> None:
    result = normalize_pandl_report(
        report_lines=[{"name": "Income", "balance": -500.0, "level": 1, "type": "income"}],
        date_from="2026-05-01",
        date_to="2026-05-16",
        source="ins.financial.report",
    )
    assert result["report_name"] == "Profit & Loss"
    assert "kpis_formatted" in result

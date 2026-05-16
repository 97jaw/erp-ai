from __future__ import annotations

from gateway.accounting_sql.post_process import post_process_balance_sheet
from gateway.balance_sheet_normalize import extract_balance_sheet_kpis, normalize_balance_sheet_report


def test_extract_balance_sheet_kpis() -> None:
    lines = [
        {"name": "Assets", "balance": 1000.0, "level": 1},
        {"name": "Liabilities", "balance": 400.0, "level": 1},
        {"name": "Equity", "balance": 600.0, "level": 1},
    ]
    kpis = extract_balance_sheet_kpis(lines)
    assert kpis["total_assets"] == 1000.0
    assert kpis["total_liabilities"] == 400.0
    assert kpis["total_equity"] == 600.0
    assert kpis["balanced"] is True


def test_post_process_balance_sheet_sql_rows() -> None:
    rows = [
        {
            "internal_group": "asset",
            "account_code": "1100",
            "account_name": "Cash",
            "debit_sum": 1000.0,
            "credit_sum": 0.0,
            "balance_sum": 1000.0,
        },
        {
            "internal_group": "liability",
            "account_code": "2100",
            "account_name": "Payables",
            "debit_sum": 0.0,
            "credit_sum": 400.0,
            "balance_sum": -400.0,
        },
        {
            "internal_group": "equity",
            "account_code": "3100",
            "account_name": "Capital",
            "debit_sum": 0.0,
            "credit_sum": 600.0,
            "balance_sum": -600.0,
        },
    ]
    result = post_process_balance_sheet(rows, as_of_date="2026-05-16", company_id=1)
    assert result["report_type"] == "balance_sheet"
    assert result["kpis"]["total_assets"] == 1000.0
    assert result["kpis"]["balanced"] is True


def test_normalize_balance_sheet_report_shape() -> None:
    result = normalize_balance_sheet_report(
        report_lines=[{"name": "Assets", "balance": 500.0, "level": 1}],
        as_of_date="2026-05-16",
        source="ins.financial.report",
    )
    assert result["report_name"] == "Balance Sheet"
    assert result["as_of_date"] == "2026-05-16"

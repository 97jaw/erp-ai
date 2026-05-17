from __future__ import annotations

from gateway.accounting_sql.post_process import post_process_report
from gateway.cost_analysis_normalize import normalize_cost_analysis


def test_normalize_cost_analysis_groups_projects() -> None:
    rows = [
        {
            "analytic_account_id": 10,
            "analytic_account_name": "Project Alpha",
            "account_code": "6001",
            "account_name": "Materials",
            "debit_sum": 1000.0,
            "credit_sum": 100.0,
            "cost_amount": 900.0,
        },
        {
            "analytic_account_id": 10,
            "analytic_account_name": "Project Alpha",
            "account_code": "6002",
            "account_name": "Labor",
            "debit_sum": 500.0,
            "credit_sum": 0.0,
            "cost_amount": 500.0,
        },
        {
            "analytic_account_id": 20,
            "analytic_account_name": "Project Beta",
            "account_code": "6001",
            "account_name": "Materials",
            "debit_sum": 200.0,
            "credit_sum": 0.0,
            "cost_amount": 200.0,
        },
    ]
    result = normalize_cost_analysis(
        rows,
        date_from="2026-01-01",
        date_to="2026-05-16",
        source="direct_sql",
    )
    assert result["project_count"] == 2
    assert result["totals"]["total_cost"] == 1600.0
    assert result["projects"]["10"]["total_cost"] == 1400.0
    assert len(result["projects"]["10"]["accounts"]) == 2


def test_post_process_cost_analysis_from_sql_rows() -> None:
    rows = [
        {
            "analytic_account_id": 5,
            "analytic_account_name": "Site A",
            "account_code": "6100",
            "account_name": "Subcontractors",
            "debit_sum": 3000.0,
            "credit_sum": 0.0,
            "cost_amount": 3000.0,
        },
    ]
    result = post_process_report(
        "cost_analysis",
        rows,
        {
            "date_from": "2026-05-01",
            "date_to": "2026-05-16",
            "company_id": 1,
        },
    )
    assert result["report_type"] == "cost_analysis"
    assert result["totals"]["total_cost"] == 3000.0

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from gateway.accounting_sql.post_process import post_process_trial_balance
from gateway.accounting_sql.query_accounting import execute_query_accounting


def test_post_process_trial_balance_balanced_totals() -> None:
    rows = [
        {
            "account_id": 1,
            "account_code": "1000",
            "account_name": "Cash",
            "debit_sum": 1000.0,
            "credit_sum": 0.0,
            "balance_sum": 1000.0,
        },
        {
            "account_id": 2,
            "account_code": "2000",
            "account_name": "Payables",
            "debit_sum": 0.0,
            "credit_sum": 1000.0,
            "balance_sum": -1000.0,
        },
    ]
    result = post_process_trial_balance(
        rows,
        date_from="2026-05-01",
        date_to="2026-05-13",
        company_id=1,
    )

    assert result["report_name"] == "Trial Balance"
    assert result["report_type"] == "trial_balance"
    assert result["source"] == "direct_sql"
    assert result["data"]["headers"] == ["Account", "Debit", "Credit", "Balance"]
    assert result["totals"]["debit"] == 1000.0
    assert result["totals"]["credit"] == 1000.0
    assert result["totals"]["balanced"] is True
    assert result["rows"][-1][0] == "Total"


def test_execute_query_accounting_requires_dsn() -> None:
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("ODOO_POSTGRES_DSN", None)
        result = execute_query_accounting(
            {"report_type": "trial_balance", "date_from": "2026-05-01", "date_to": "2026-05-13"}
        )
    assert result["error"] == "accounting_sql_unavailable"


def test_execute_query_accounting_rejects_unknown_report_type() -> None:
    result = execute_query_accounting(
        {"report_type": "unknown_report", "date_from": "2026-05-01", "date_to": "2026-05-13"}
    )
    assert result["error"] == "unsupported_report_type"


@patch("gateway.accounting_sql.query_accounting.accounting_cursor")
def test_execute_query_accounting_trial_balance(mock_cursor_ctx: MagicMock) -> None:
    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [{"column_name": "internal_group"}, {"column_name": "type"}],
        [
            {
                "account_id": 10,
                "account_code": "4000",
                "account_name": "Revenue",
                "debit_sum": 0.0,
                "credit_sum": 500.0,
                "balance_sum": -500.0,
            },
        ],
    ]
    mock_cursor_ctx.return_value.__enter__.return_value = cursor

    with patch.dict(os.environ, {"ODOO_POSTGRES_DSN": "postgresql://test"}, clear=False):
        result = execute_query_accounting(
            {
                "report_type": "trial_balance",
                "date_from": "2026-05-01",
                "date_to": "2026-05-13",
                "company_id": 1,
            }
        )

    assert result.get("error") is None
    assert result["report_type"] == "trial_balance"
    assert result["row_count"] == 1
    assert result["totals"]["credit"] == 500.0
    assert cursor.execute.call_count >= 2
    trial_sql = cursor.execute.call_args_list[-1][0][0]
    assert "account_move_line" in trial_sql
    assert "am.state = 'posted'" in trial_sql

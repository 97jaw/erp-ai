from __future__ import annotations

from unittest.mock import MagicMock

from gateway.aggregate_tools import sql_aggregate, synthesize_trial_balance


def test_sql_aggregate_normalizes_sum_fields() -> None:
    adapter = MagicMock()
    adapter.read_group.return_value = [
        {"account_id": [1, "Cash"], "debit_sum": 100.0, "credit_sum": 25.0},
    ]

    result = sql_aggregate(
        adapter,
        {
            "model": "account.move.line",
            "aggregates": ["debit", "credit"],
            "group_by": ["account_id"],
        },
    )

    assert result["row_count"] == 1
    assert result["rows"][0]["debit"] == 100.0
    assert result["rows"][0]["credit"] == 25.0
    assert result["synthesized"] is True


def test_synthesize_trial_balance_shapes_table() -> None:
    adapter = MagicMock()
    adapter.read_group.return_value = [
        {"account_id": [1, "Cash"], "debit_sum": 100.0, "credit_sum": 25.0},
        {"account_id": [2, "Payables"], "debit_sum": 0.0, "credit_sum": 0.0},
    ]

    result = synthesize_trial_balance(adapter, "2026-05-01", "2026-05-13")

    assert result["report_name"] == "Trial Balance"
    assert result["data"]["headers"][0] == "Account"
    assert result["totals"]["debit"] == 100.0
    assert result["totals"]["credit"] == 25.0
    assert len(result["rows"]) == 2  # one account + Total row

from __future__ import annotations

from gateway.accounting_sql.post_process import post_process_general_ledger
from gateway.general_ledger_normalize import normalize_general_ledger


def test_normalize_general_ledger_totals() -> None:
    raw = {
        "1100": {
            "name": "Cash",
            "debit": 100.0,
            "credit": 25.0,
            "balance": 75.0,
            "lines": [
                {"date": "2026-05-01", "move_name": "INV/1", "partner": "A", "debit": 100, "credit": 0, "balance": 100},
                {"date": "2026-05-02", "move_name": "BILL/1", "partner": "B", "debit": 0, "credit": 25, "balance": 75},
            ],
        },
    }
    result = normalize_general_ledger(
        raw,
        date_from="2026-05-01",
        date_to="2026-05-16",
        source="ins.general.ledger",
    )
    assert result["account_count"] == 1
    assert result["line_count"] == 2
    assert result["totals"]["debit"] == 100.0
    assert result["totals"]["credit"] == 25.0


def test_post_process_general_ledger_sql_rows() -> None:
    rows = [
        {
            "account_code": "1100",
            "account_name": "Cash",
            "line_date": "2026-05-01",
            "move_name": "M1",
            "partner_name": "Partner",
            "debit": 50.0,
            "credit": 0.0,
        },
        {
            "account_code": "1100",
            "account_name": "Cash",
            "line_date": "2026-05-02",
            "move_name": "M2",
            "partner_name": "Partner",
            "debit": 0.0,
            "credit": 20.0,
        },
    ]
    result = post_process_general_ledger(
        rows,
        date_from="2026-05-01",
        date_to="2026-05-16",
        company_id=1,
    )
    assert result["report_type"] == "general_ledger"
    assert result["accounts"]["1100"]["debit"] == 50.0
    assert result["accounts"]["1100"]["credit"] == 20.0
    assert len(result["accounts"]["1100"]["lines"]) == 2

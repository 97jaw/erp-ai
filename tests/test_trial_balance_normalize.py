from __future__ import annotations

from gateway.trial_balance_normalize import normalize_ins_trial_balance


def test_normalize_ins_trial_balance_uses_subtotal_period_columns() -> None:
    result = normalize_ins_trial_balance(
        date_from="2026-05-01",
        date_to="2026-05-16",
        filters={},
        account_lines={
            "1501": {
                "code": "1501",
                "name": "VAT INPUT",
                "debit": 100.0,
                "credit": 0.0,
                "balance": 100.0,
                "ending_debit": 500.0,
                "ending_credit": 0.0,
            },
        },
        retained={},
        subtotal={
            "SUBTOTAL": {
                "initial_debit": 10.0,
                "initial_credit": 5.0,
                "debit": 1000.0,
                "credit": 1000.0,
                "ending_debit": 2000.0,
                "ending_credit": 2000.0,
            },
        },
    )

    assert result["source"] == "ins.trial.balance"
    assert result["totals"]["debit"] == 1000.0
    assert result["totals"]["credit"] == 1000.0
    assert result["totals"]["balanced"] is True
    assert result["totals"]["ending_debit"] == 2000.0

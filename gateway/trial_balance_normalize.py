from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def _f(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def normalize_ins_trial_balance(
    *,
    date_from: str,
    date_to: str,
    filters: dict[str, Any] | None,
    account_lines: Any,
    retained: dict[str, Any] | None,
    subtotal: dict[str, Any] | None,
) -> dict[str, Any]:
    """Shape ins.trial.balance wizard output to OOA trial balance contract."""
    sub = (subtotal or {}).get("SUBTOTAL") or {}
    accounts = account_lines if isinstance(account_lines, dict) else {}

    table_rows: list[list[Any]] = []
    for code, acc in accounts.items():
        if not isinstance(acc, dict):
            continue
        period_debit = _f(acc.get("debit"))
        period_credit = _f(acc.get("credit"))
        period_balance = _f(acc.get("balance"))
        if period_debit == 0 and period_credit == 0 and period_balance == 0:
            ending_balance = _f(acc.get("ending_balance"))
            if ending_balance == 0:
                continue
        label = acc.get("name") or code
        account_code = acc.get("code") or code
        display = f"{account_code} {label}".strip() if account_code else str(label)
        table_rows.append([
            display,
            period_debit,
            period_credit,
            period_balance,
        ])

    period_debit = _f(sub.get("debit"))
    period_credit = _f(sub.get("credit"))
    table_rows.append(["Total", period_debit, period_credit, _f(sub.get("balance"))])

    totals = {
        "initial_debit": _f(sub.get("initial_debit")),
        "initial_credit": _f(sub.get("initial_credit")),
        "initial_balance": _f(sub.get("initial_balance")),
        "debit": period_debit,
        "credit": period_credit,
        "period_balance": _f(sub.get("balance")),
        "ending_debit": _f(sub.get("ending_debit")),
        "ending_credit": _f(sub.get("ending_credit")),
        "ending_balance": _f(sub.get("ending_balance")),
        "difference": round(period_debit - period_credit, 2),
        "balanced": abs(period_debit - period_credit) < 0.05,
    }

    return {
        "report_type": "trial_balance",
        "report_name": "Trial Balance",
        "date_from": date_from,
        "date_to": date_to,
        "row_count": max(len(table_rows) - 1, 0),
        "totals": totals,
        "totals_formatted": {
            "period_debit": format_currency(period_debit),
            "period_credit": format_currency(period_credit),
            "ending_debit": format_currency(totals["ending_debit"]),
            "ending_credit": format_currency(totals["ending_credit"]),
        },
        "rows": table_rows,
        "data": {
            "headers": ["Account", "Period Debit", "Period Credit", "Period Balance"],
            "rows": table_rows,
        },
        "accounts": accounts,
        "retained": retained or {},
        "subtotal": sub,
        "filters": filters or {},
        "source": "ins.trial.balance",
        "synthesized": False,
        "quality_note": (
            "Period debits and credits match Odoo Trial Balance period columns."
            if totals["balanced"]
            else "Period totals differ — align date range with Odoo UI filters."
        ),
    }

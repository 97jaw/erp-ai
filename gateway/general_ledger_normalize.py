from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def _f(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _clean_line(line: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(line.get("date") or line.get("ldate") or ""),
        "move_name": line.get("move_name") or "",
        "partner": line.get("partner") or line.get("partner_name") or "",
        "debit": _f(line.get("debit")),
        "credit": _f(line.get("credit")),
        "balance": _f(line.get("balance")),
    }


def normalize_general_ledger(
    raw_accounts: dict[str, Any],
    *,
    date_from: str,
    date_to: str,
    source: str,
    filters: dict[str, Any] | None = None,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accounts: dict[str, Any] = {}
    total_debit = 0.0
    total_credit = 0.0
    line_count = 0

    for code, account in (raw_accounts or {}).items():
        if not isinstance(account, dict):
            continue
        lines = account.get("lines") or []
        clean_lines = [_clean_line(line) for line in lines if isinstance(line, dict)]
        debit = _f(account.get("debit"))
        credit = _f(account.get("credit"))
        balance = _f(account.get("balance"))
        if not clean_lines and debit == 0 and credit == 0 and balance == 0:
            continue
        key = str(code)
        accounts[key] = {
            "name": account.get("name") or key,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "lines": clean_lines,
        }
        total_debit += debit
        total_credit += credit
        line_count += len(clean_lines)

    table_rows: list[list[Any]] = []
    for code, account in sorted(accounts.items(), key=lambda item: item[0]):
        label = f"{code} {account['name']}".strip()
        table_rows.append([label, account["debit"], account["credit"], account["balance"]])
    table_rows.append([
        "Total",
        round(total_debit, 2),
        round(total_credit, 2),
        round(total_debit - total_credit, 2),
    ])

    return {
        "report_type": "general_ledger",
        "report_name": "General Ledger",
        "date_from": date_from,
        "date_to": date_to,
        "accounts": accounts,
        "account_count": len(accounts),
        "line_count": line_count,
        "totals": {
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "difference": round(total_debit - total_credit, 2),
        },
        "totals_formatted": {
            "debit": format_currency(total_debit),
            "credit": format_currency(total_credit),
        },
        "data": {
            "headers": ["Account", "Debit", "Credit", "Balance"],
            "rows": table_rows,
        },
        "filters": filters or {},
        "applied_filters": applied_filters or {},
        "source": source,
        "synthesized": False,
    }

from __future__ import annotations

from typing import Any

from gateway.balance_sheet_normalize import extract_balance_sheet_kpis, normalize_balance_sheet_report
from gateway.general_ledger_normalize import normalize_general_ledger
from gateway.pandl_normalize import extract_pandl_kpis, normalize_pandl_report
from gateway.quality_formatting import format_currency


def _round_amount(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def post_process_trial_balance(
    rows: list[dict[str, Any]],
    *,
    date_from: str,
    date_to: str,
    company_id: int,
) -> dict[str, Any]:
    table_rows: list[list[Any]] = []
    total_debit = 0.0
    total_credit = 0.0

    for row in rows:
        debit = _round_amount(row.get("debit_sum"))
        credit = _round_amount(row.get("credit_sum"))
        balance = _round_amount(row.get("balance_sum", debit - credit))
        if debit == 0 and credit == 0:
            continue
        label = row.get("account_name") or row.get("account_code") or row.get("account_id")
        code = row.get("account_code") or ""
        display = f"{code} {label}".strip() if code else str(label)
        table_rows.append([display, debit, credit, balance])
        total_debit += debit
        total_credit += credit

    table_rows.append(["Total", round(total_debit, 2), round(total_credit, 2), round(total_debit - total_credit, 2)])

    balanced = abs(total_debit - total_credit) < 0.05
    return {
        "report_type": "trial_balance",
        "report_name": "Trial Balance",
        "date_from": date_from,
        "date_to": date_to,
        "company_id": company_id,
        "row_count": max(len(table_rows) - 1, 0),
        "totals": {
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "difference": round(total_debit - total_credit, 2),
            "balanced": balanced,
        },
        "totals_formatted": {
            "debit": format_currency(total_debit),
            "credit": format_currency(total_credit),
            "difference": format_currency(total_debit - total_credit),
        },
        "rows": table_rows,
        "data": {
            "headers": ["Account", "Debit", "Credit", "Balance"],
            "rows": table_rows,
        },
        "source": "direct_sql",
        "synthesized": False,
        "quality_note": (
            "Trial balance debits and credits are balanced."
            if balanced
            else "Trial balance totals differ — review date range and posted entries."
        ),
    }


def post_process_pandl(
    rows: list[dict[str, Any]],
    *,
    date_from: str,
    date_to: str,
    company_id: int,
) -> dict[str, Any]:
    report_lines: list[dict[str, Any]] = []
    income_total = 0.0
    expense_total = 0.0

    for row in rows:
        group = (row.get("internal_group") or "").lower()
        balance = _round_amount(row.get("balance_sum"))
        code = row.get("account_code") or ""
        name = row.get("account_name") or ""
        if balance == 0:
            continue
        if group == "income":
            income_total += abs(balance)
        elif group == "expense":
            expense_total += abs(balance)
        report_lines.append({
            "name": f"{code} {name}".strip(),
            "balance": balance,
            "debit": _round_amount(row.get("debit_sum")),
            "credit": _round_amount(row.get("credit_sum")),
            "level": 3,
            "type": group,
            "style": "detail",
        })

    summary_lines = [
        {"name": "Income", "balance": -income_total, "debit": 0, "credit": 0, "level": 1, "type": "income", "style": "main"},
        {"name": "Expenses", "balance": expense_total, "debit": 0, "credit": 0, "level": 1, "type": "expense", "style": "main"},
    ]
    merged_lines = summary_lines + report_lines
    result = normalize_pandl_report(
        report_lines=merged_lines,
        date_from=date_from,
        date_to=date_to,
        source="direct_sql",
    )
    result["company_id"] = company_id
    result["kpis"] = extract_pandl_kpis(summary_lines)
    result["kpis"]["net_profit"] = round(result["kpis"]["total_income"] - result["kpis"]["total_expense"], 2)
    if result["kpis"]["total_income"]:
        result["kpis"]["margin"] = round(
            result["kpis"]["net_profit"] / result["kpis"]["total_income"] * 100,
            2,
        )
    return result


def _section_balance(group: str, debit: float, credit: float, raw_balance: float) -> float:
    group = (group or "").lower()
    if group == "asset":
        return round(debit - credit, 2)
    if group in {"liability", "equity"}:
        return round(credit - debit, 2)
    return _round_amount(raw_balance)


def post_process_balance_sheet(
    rows: list[dict[str, Any]],
    *,
    as_of_date: str,
    company_id: int,
) -> dict[str, Any]:
    report_lines: list[dict[str, Any]] = []
    section_totals = {"asset": 0.0, "liability": 0.0, "equity": 0.0}

    for row in rows:
        group = (row.get("internal_group") or "").lower()
        if group not in section_totals:
            continue
        debit = _round_amount(row.get("debit_sum"))
        credit = _round_amount(row.get("credit_sum"))
        balance = _section_balance(group, debit, credit, row.get("balance_sum"))
        if balance == 0:
            continue
        code = row.get("account_code") or ""
        name = row.get("account_name") or ""
        section_totals[group] += balance
        report_lines.append({
            "name": f"{code} {name}".strip(),
            "balance": balance,
            "debit": debit,
            "credit": credit,
            "level": 3,
            "type": group,
            "style": "detail",
        })

    summary_lines = [
        {"name": "Assets", "balance": section_totals["asset"], "level": 1, "type": "asset", "style": "main"},
        {
            "name": "Liabilities",
            "balance": section_totals["liability"],
            "level": 1,
            "type": "liability",
            "style": "main",
        },
        {"name": "Equity", "balance": section_totals["equity"], "level": 1, "type": "equity", "style": "main"},
    ]
    merged_lines = summary_lines + report_lines
    result = normalize_balance_sheet_report(
        report_lines=merged_lines,
        as_of_date=as_of_date,
        source="direct_sql",
    )
    result["company_id"] = company_id
    result["kpis"] = extract_balance_sheet_kpis(summary_lines)
    return result


def post_process_general_ledger(
    rows: list[dict[str, Any]],
    *,
    date_from: str,
    date_to: str,
    company_id: int,
) -> dict[str, Any]:
    accounts: dict[str, Any] = {}
    for row in rows:
        code = str(row.get("account_code") or "unknown")
        if code not in accounts:
            accounts[code] = {
                "name": row.get("account_name") or code,
                "debit": 0.0,
                "credit": 0.0,
                "balance": 0.0,
                "lines": [],
            }
        debit = _round_amount(row.get("debit"))
        credit = _round_amount(row.get("credit"))
        running = _round_amount(accounts[code]["balance"] + debit - credit)
        accounts[code]["debit"] = round(accounts[code]["debit"] + debit, 2)
        accounts[code]["credit"] = round(accounts[code]["credit"] + credit, 2)
        accounts[code]["balance"] = running
        accounts[code]["lines"].append({
            "date": str(row.get("line_date") or ""),
            "move_name": row.get("move_name") or "",
            "partner": row.get("partner_name") or "",
            "debit": debit,
            "credit": credit,
            "balance": running,
        })

    result = normalize_general_ledger(
        accounts,
        date_from=date_from,
        date_to=date_to,
        source="direct_sql",
    )
    result["company_id"] = company_id
    return result


def post_process_report(
    report_type: str,
    rows: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    if report_type == "trial_balance":
        return post_process_trial_balance(
            rows,
            date_from=params["date_from"],
            date_to=params["date_to"],
            company_id=int(params.get("company_id", 1)),
        )
    if report_type == "pandl":
        return post_process_pandl(
            rows,
            date_from=params["date_from"],
            date_to=params["date_to"],
            company_id=int(params.get("company_id", 1)),
        )
    if report_type == "balance_sheet":
        return post_process_balance_sheet(
            rows,
            as_of_date=params["date_to"],
            company_id=int(params.get("company_id", 1)),
        )
    if report_type == "general_ledger":
        return post_process_general_ledger(
            rows,
            date_from=params["date_from"],
            date_to=params["date_to"],
            company_id=int(params.get("company_id", 1)),
        )
    raise NotImplementedError(f"Post-processing not implemented yet: {report_type}")

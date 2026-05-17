from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def _f(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def normalize_cost_analysis(
    rows: list[dict[str, Any]],
    *,
    date_from: str,
    date_to: str,
    source: str,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    projects: dict[str, Any] = {}
    table_rows: list[list[Any]] = []

    for row in rows:
        analytic_id = row.get("analytic_account_id")
        project_key = str(analytic_id) if analytic_id else "0"
        project_name = str(
            row.get("analytic_account_name")
            or row.get("project_name")
            or ("Unallocated" if not analytic_id else project_key)
        )
        if project_key not in projects:
            projects[project_key] = {
                "analytic_account_id": analytic_id,
                "name": project_name,
                "total_cost": 0.0,
                "accounts": [],
            }

        debit = _f(row.get("debit_sum", row.get("debit")))
        credit = _f(row.get("credit_sum", row.get("credit")))
        cost = _f(row.get("cost_amount", row.get("cost", debit - credit)))
        account_code = str(row.get("account_code") or "")
        account_name = str(row.get("account_name") or account_code)
        account_label = f"{account_code} {account_name}".strip()

        projects[project_key]["accounts"].append({
            "account_id": row.get("account_id"),
            "code": account_code,
            "name": account_name,
            "debit": debit,
            "credit": credit,
            "cost": cost,
        })
        projects[project_key]["total_cost"] = round(
            projects[project_key]["total_cost"] + cost,
            2,
        )
        table_rows.append([project_name, account_label, debit, credit, cost])

    table_rows.sort(key=lambda item: float(item[4]), reverse=True)
    grand_total = round(sum(project["total_cost"] for project in projects.values()), 2)
    if table_rows:
        table_rows.append(["Total", "", "", "", grand_total])

    return {
        "report_type": "cost_analysis",
        "report_name": "Cost Analysis",
        "date_from": date_from,
        "date_to": date_to,
        "projects": projects,
        "project_count": len(projects),
        "line_count": max(len(table_rows) - (1 if table_rows else 0), 0),
        "totals": {"total_cost": grand_total},
        "totals_formatted": {"total_cost": format_currency(grand_total)},
        "data": {
            "headers": ["Project", "Account", "Debit", "Credit", "Cost"],
            "rows": table_rows,
        },
        "applied_filters": applied_filters or {},
        "source": source,
        "synthesized": False,
    }

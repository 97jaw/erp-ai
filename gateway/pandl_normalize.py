from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def extract_pandl_kpis(lines: list[dict[str, Any]]) -> dict[str, float]:
    kpis = {
        "total_income": 0.0,
        "total_expense": 0.0,
        "net_profit": 0.0,
        "margin": 0.0,
    }
    if not lines:
        return kpis

    for line in lines:
        name = (line.get("name") or "").lower().strip()
        balance = float(line.get("balance", 0) or 0)
        level = int(line.get("level", 0) or 0)
        if level != 1:
            continue
        if any(key in name for key in ("income", "revenue", "sales")):
            kpis["total_income"] = abs(balance)
        elif any(key in name for key in ("expense", "cost", "expenditure")):
            kpis["total_expense"] = abs(balance)

    kpis["net_profit"] = round(kpis["total_income"] - kpis["total_expense"], 2)
    kpis["margin"] = round(
        (kpis["net_profit"] / kpis["total_income"] * 100) if kpis["total_income"] else 0.0,
        2,
    )
    return kpis


def normalize_pandl_report(
    *,
    report_lines: list[dict[str, Any]],
    date_from: str,
    date_to: str,
    source: str,
    initial_balance: float = 0.0,
    current_balance: float = 0.0,
    ending_balance: float = 0.0,
    currency: Any = None,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_lines = []
    for line in report_lines:
        clean_lines.append({
            "name": line.get("name", ""),
            "balance": float(line.get("balance", 0) or 0),
            "debit": float(line.get("debit", 0) or 0),
            "credit": float(line.get("credit", 0) or 0),
            "level": int(line.get("level", 0) or 0),
            "type": line.get("type") or line.get("fin_report_type", ""),
            "style": line.get("style") or line.get("style_type", "main"),
        })

    kpis = extract_pandl_kpis(clean_lines)
    income_lines = [line for line in clean_lines if line["level"] >= 2 and line["balance"] != 0]
    expense_lines = income_lines

    return {
        "report_type": "pandl",
        "report_name": "Profit & Loss",
        "date_from": date_from,
        "date_to": date_to,
        "report_lines": clean_lines,
        "income_lines": [line for line in clean_lines if "income" in (line.get("type") or "").lower()],
        "expense_lines": [line for line in clean_lines if "expense" in (line.get("type") or "").lower()],
        "kpis": kpis,
        "kpis_formatted": {
            "total_income": format_currency(kpis["total_income"]),
            "total_expense": format_currency(kpis["total_expense"]),
            "net_profit": format_currency(kpis["net_profit"]),
            "margin": f"{kpis['margin']:.2f}%",
        },
        "currency": currency,
        "initial_balance": initial_balance,
        "current_balance": current_balance,
        "ending_balance": ending_balance,
        "source": source,
        "synthesized": False,
        "applied_filters": applied_filters or {},
        "quality_note": (
            f"Net profit {format_currency(kpis['net_profit'])} "
            f"({kpis['margin']:.2f}% margin on income)."
        ),
    }

from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def extract_balance_sheet_kpis(lines: list[dict[str, Any]]) -> dict[str, float]:
    kpis = {
        "total_assets": 0.0,
        "total_liabilities": 0.0,
        "total_equity": 0.0,
        "balanced": False,
    }
    if not lines:
        return kpis

    for line in lines:
        name = (line.get("name") or "").lower().strip()
        balance = float(line.get("balance", 0) or 0)
        level = int(line.get("level", 0) or 0)
        if level != 1:
            continue
        if "asset" in name:
            kpis["total_assets"] = abs(balance)
        elif "liabilit" in name:
            kpis["total_liabilities"] = abs(balance)
        elif "equity" in name:
            kpis["total_equity"] = abs(balance)

    liabilities_equity = kpis["total_liabilities"] + kpis["total_equity"]
    kpis["balanced"] = abs(kpis["total_assets"] - liabilities_equity) < 0.05
    return kpis


def normalize_balance_sheet_report(
    *,
    report_lines: list[dict[str, Any]],
    as_of_date: str,
    source: str,
    initial_balance: float = 0.0,
    current_balance: float = 0.0,
    ending_balance: float = 0.0,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kpis = extract_balance_sheet_kpis(report_lines)
    return {
        "report_type": "balance_sheet",
        "report_name": "Balance Sheet",
        "as_of_date": as_of_date,
        "date_from": "1900-01-01",
        "date_to": as_of_date,
        "report_lines": report_lines,
        "kpis": kpis,
        "kpis_formatted": {
            "total_assets": format_currency(kpis["total_assets"]),
            "total_liabilities": format_currency(kpis["total_liabilities"]),
            "total_equity": format_currency(kpis["total_equity"]),
        },
        "initial_balance": initial_balance,
        "current_balance": current_balance,
        "ending_balance": ending_balance,
        "source": source,
        "synthesized": False,
        "applied_filters": applied_filters or {},
        "quality_note": (
            "Assets equal liabilities plus equity."
            if kpis["balanced"]
            else "Balance sheet sections do not balance — verify as-of date and filters."
        ),
    }

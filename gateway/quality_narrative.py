from __future__ import annotations

import re
from typing import Any

from gateway.quality_formatting import format_currency, format_percentage, humanize_group_label

_PERIOD_IN_QUERY_RE = re.compile(
    r"\b("
    r"this\s+year|last\s+year|ytd|year\s+to\s+date|"
    r"this\s+month|last\s+month|"
    r"q[1-4]|quarter|"
    r"last\s+\d+\s+months?"
    r")\b",
    re.IGNORECASE,
)

_LEGACY_PERIOD_PHRASE = "for the selected period"


def user_asked_for_calendar_period(message: str = "") -> bool:
    """Return True when the user mentioned a date range in the query."""
    return bool(_PERIOD_IN_QUERY_RE.search(message or ""))


def is_legacy_period_expense_text(text: str = "") -> bool:
    """Detect generic legacy synthesizer copy that should be replaced."""
    lowered = (text or "").lower()
    return _LEGACY_PERIOD_PHRASE in lowered


def narrate_project_expense_summary(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Build executive summary text for mobile project expense payloads."""
    project_name = payload.get("project_name") or "Project"
    total = float(payload.get("total_expenses") or 0)
    wo_amount = float(payload.get("wo_amount") or 0)
    spend_pct = float(payload.get("spend_percent_of_wo") or 0)

    if payload.get("is_over_budget"):
        status = "over budget"
    elif spend_pct > 95:
        status = "near the W.O limit"
    else:
        status = "on track"

    if language == "ar":
        lead = (
            f"{project_name}: إجمالي المصروف {format_currency(total)} "
            f"({format_percentage(spend_pct)} من W.O {format_currency(wo_amount)}). "
            f"الحالة: {status}."
        )
    else:
        lead = (
            f"{project_name}: total spend is {format_currency(total)} "
            f"({format_percentage(spend_pct)} of W.O {format_currency(wo_amount)}). "
            f"Status: {status}."
        )

    top_expenses = payload.get("top_expenses") or []
    trade_bits: list[str] = []
    for item in top_expenses[:3]:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("label") or "Other"
        amount = float(item.get("amount") or 0)
        percent = item.get("percent")
        if percent is not None:
            trade_bits.append(f"{name} ({format_currency(amount)}, {format_percentage(float(percent))})")
        else:
            trade_bits.append(f"{name} ({format_currency(amount)})")

    parts = [lead]
    if trade_bits:
        if language == "ar":
            parts.append(f"أبرز الفئات: {', '.join(trade_bits)}.")
        else:
            parts.append(f"Top trade categories: {', '.join(trade_bits)}.")

    context_message = user_message or str(payload.get("project_name") or "")
    if user_asked_for_calendar_period(context_message):
        if language == "ar":
            parts.append(
                "ملاحظة: هذا ملخص مصروفات المشروع الكامل (حسب W.O) كما في تطبيق Odoo — "
                "وليس مفلتراً حسب السنة أو الفترة."
            )
        else:
            parts.append(
                "Note: this is the full project expense summary (W.O-based), matching the Odoo "
                "mobile view — not filtered to a calendar period."
            )

    return " ".join(parts)


def _payload_from_expense_visualization(visualization: dict[str, Any]) -> dict[str, Any]:
    kpis = visualization.get("kpis") or {}
    wo = (kpis.get("wo_amount") or {}).get("value")
    total = (kpis.get("total_expenses") or {}).get("value")
    spend = visualization.get("spend_percent_of_wo")
    if spend is None:
        spend = (kpis.get("spend_pct") or {}).get("value")
    return {
        "project_name": visualization.get("project_name") or visualization.get("label"),
        "wo_amount": wo,
        "total_expenses": total,
        "spend_percent_of_wo": spend,
        "is_over_budget": visualization.get("is_over_budget"),
        "top_expenses": visualization.get("top_expenses") or [],
    }


def _bar_chart_rows(visualization: dict[str, Any]) -> list[dict[str, Any]]:
    data = visualization.get("data") or {}
    rows = data.get("rows") or []
    if rows:
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            label = humanize_group_label(row[0])
            try:
                value = float(row[1] or 0)
            except (TypeError, ValueError, IndexError):
                value = 0.0
            parsed.append({"label": label, "value": value})
        return parsed

    labels = data.get("labels") or []
    values = data.get("values") or []
    return [
        {"label": humanize_group_label(label), "value": float(values[index] or 0)}
        for index, label in enumerate(labels)
    ]


def generate_narrative(
    user_message: str,
    visualization: dict[str, Any] | None,
    tool_results: list[Any],
    language: str = "en",
) -> str:
    if not visualization:
        for result in reversed(tool_results):
            if not isinstance(result, dict) or result.get("error"):
                continue
            if result.get("quality_warning"):
                return str(result["quality_warning"])
            if result.get("groups") and not result.get("groups"):
                return (
                    "No matching records were found for that period. "
                    "Try a wider date range or confirm the filters."
                )
        return ""

    visual_type = visualization.get("visual_type")
    if visual_type == "PROJECT_EXPENSE_SUMMARY":
        for result in reversed(tool_results):
            if isinstance(result, dict) and result.get("_source") == "project_expense_summary_mobile":
                return narrate_project_expense_summary(
                    result,
                    user_message=user_message,
                    language=language,
                )
        return narrate_project_expense_summary(
            _payload_from_expense_visualization(visualization),
            user_message=user_message,
            language=language,
        )

    if visual_type == "BAR_CHART":
        rows = _bar_chart_rows(visualization)
        rows = [row for row in rows if row["value"] > 0]
        if not rows:
            return (
                "I did not find any positive values for that comparison. "
                "The posted records for this period may be empty or filtered out."
            )
        rows.sort(key=lambda item: item["value"], reverse=True)
        total = sum(row["value"] for row in rows)
        leader = rows[0]
        leader_share = (leader["value"] / total) * 100 if total else 0
        if language == "ar":
            return (
                f"يتصدر {leader['label']} بقيمة {format_currency(leader['value'])} "
                f"({format_percentage(leader_share)} من الإجمالي). "
                f"إجمالي النتائج المعروضة {format_currency(total)}."
            )
        return (
            f"{leader['label']} leads with {format_currency(leader['value'])} "
            f"({format_percentage(leader_share)} of the total). "
            f"The visible results total {format_currency(total)}."
        )

    if visual_type == "DATA_TABLE":
        rows = (visualization.get("data") or {}).get("rows") or []
        if rows:
            return (
                f"Here are {len(rows)} rows for your request. "
                "Use the table to review the ranked or grouped results."
            )

    if visual_type == "KPI_CARD":
        value = visualization.get("value")
        label = visualization.get("label") or "Result"
        unit = visualization.get("unit") or ""
        if unit.upper() == "AED":
            return f"{label}: {format_currency(value)}."
        return f"{label}: {format_number(value)}." if value is not None else f"{label} is ready."

    if visual_type == "GROUPED_TABLE":
        groups = (visualization.get("data") or {}).get("groups") or []
        if groups:
            return (
                f"The breakdown includes {len(groups)} top-level groups. "
                "Expand a group to review the nested detail."
            )

    return ""


def format_number(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)

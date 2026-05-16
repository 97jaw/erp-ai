from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency, format_percentage, humanize_group_label


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

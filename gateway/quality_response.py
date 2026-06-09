from __future__ import annotations

import logging
from typing import Any

from gateway.quality_formatting import (
    format_currency,
    humanize_aggregate_spec,
    humanize_group_label,
)
from gateway.quality_intent import detect_query_intent
from gateway.quality_narrative import generate_narrative, is_legacy_period_expense_text
from gateway.quality_validation import validate_response_quality
from gateway.progressive_disclosure import apply_progressive_disclosure
from gateway.core.project_expense_routing import is_project_expense_tool_result
from gateway.visualization_builder import (
    build_visualization_from_tool_results,
    is_renderable_visualization,
)

logger = logging.getLogger(__name__)

QUALITY_METRICS: dict[str, int] = {
    "responses": 0,
    "quality_pass": 0,
    "quality_fail": 0,
}


def record_quality_result(passed: bool) -> None:
    QUALITY_METRICS["responses"] += 1
    if passed:
        QUALITY_METRICS["quality_pass"] += 1
    else:
        QUALITY_METRICS["quality_fail"] += 1


def polish_visualization(
    visualization: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    polished = dict(visualization)
    visual_type = polished.get("visual_type")
    data = dict(polished.get("data") or {})
    unit = polished.get("unit")

    if visual_type == "BAR_CHART":
        rows = data.get("rows") or []
        labels = data.get("labels") or []
        values = data.get("values") or []
        cleaned_rows: list[list[Any]] = []
        cleaned_labels: list[str] = []
        cleaned_values: list[float] = []
        formatted_values: list[str] = []

        source_rows = rows or [
            [labels[index], values[index]]
            for index in range(min(len(labels), len(values)))
        ]
        for row in source_rows:
            label: Any
            raw_value: Any
            if isinstance(row, dict):
                label = row.get("label") or row.get("name") or row.get("category")
                raw_value = row.get("value", row.get("amount", row.get("total", 0)))
            elif isinstance(row, (list, tuple)) and row:
                label = row[0]
                raw_value = row[1] if len(row) > 1 else 0
            else:
                continue
            label = humanize_group_label(label)
            try:
                value = float(raw_value or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value <= 0:
                continue
            cleaned_rows.append([label, value])
            cleaned_labels.append(label)
            cleaned_values.append(value)
            formatted_values.append(
                format_currency(value) if unit == "AED" or intent.get("revenue") else f"{value:,.0f}"
            )

        cleaned_rows.sort(key=lambda item: float(item[1] or 0), reverse=True)
        cleaned_labels = [str(row[0]) for row in cleaned_rows]
        cleaned_values = [float(row[1] or 0) for row in cleaned_rows]
        formatted_values = [
            format_currency(value) if unit == "AED" or intent.get("revenue") else f"{value:,.0f}"
            for value in cleaned_values
        ]

        data["rows"] = cleaned_rows
        data["labels"] = cleaned_labels
        data["values"] = cleaned_values
        data["formatted_values"] = formatted_values
        polished["data"] = data
        polished["value"] = len(cleaned_rows)
        if intent.get("comparison"):
            polished["visual_type"] = "BAR_CHART"

    if visual_type == "GROUPED_TABLE":
        groups = data.get("groups") or []
        data["groups"] = _polish_group_nodes(groups)
        polished["data"] = data

    if visual_type == "DATA_TABLE":
        headers = data.get("headers") or []
        data["headers"] = [humanize_aggregate_spec(header) for header in headers]
        rows = data.get("rows") or []
        cleaned_rows = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            label = humanize_group_label(row[0])
            if label == "Unassigned":
                continue
            cleaned_rows.append([label, *row[1:]])
        data["rows"] = cleaned_rows
        polished["data"] = data

    return polished


def _polish_group_nodes(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    polished: list[dict[str, Any]] = []
    for group in groups:
        name = humanize_group_label(group.get("name"))
        if name == "Unassigned":
            continue
        aggregates = {
            humanize_aggregate_spec(key): value
            for key, value in (group.get("aggregates") or {}).items()
        }
        if all(float(value or 0) == 0 for value in aggregates.values() if isinstance(value, (int, float))):
            continue
        node = {
            "name": name,
            "aggregates": aggregates,
        }
        children = _polish_group_nodes(group.get("children") or [])
        if children:
            node["children"] = children
        polished.append(node)
    return polished


def _prefer_project_expense_tool_visualization(
    tool_names: list[str],
    tool_results: list[Any],
) -> dict[str, Any] | None:
    if not tool_names or not any(is_project_expense_tool_result(result) for result in tool_results):
        return None
    tool_visual = build_visualization_from_tool_results(tool_names, tool_results)
    if tool_visual and is_renderable_visualization(tool_visual):
        return tool_visual
    return None


def polish_agent_response(
    user_message: str,
    clean_text: str,
    visualization: dict[str, Any] | None,
    tool_names: list[str],
    tool_results: list[Any],
    language: str,
) -> tuple[str, dict[str, Any] | None]:
    intent = detect_query_intent(user_message)

    expense_visual = _prefer_project_expense_tool_visualization(tool_names, tool_results)
    has_expense_tool = any(is_project_expense_tool_result(result) for result in tool_results)
    if expense_visual is not None:
        visualization = expense_visual
    elif visualization is None and tool_names:
        visualization = build_visualization_from_tool_results(tool_names, tool_results)

    if visualization:
        visualization = polish_visualization(visualization, intent)
        preferred = intent.get("visual_type")
        if preferred == "BAR_CHART" and visualization.get("visual_type") in {"GROUPED_TABLE", "DATA_TABLE"}:
            regrouped = _grouped_table_to_bar_chart(visualization)
            if regrouped:
                visualization = regrouped
            elif intent.get("comparison"):
                visualization["visual_type"] = "BAR_CHART"

    should_refresh_expense_text = has_expense_tool and (
        not clean_text.strip()
        or is_legacy_period_expense_text(clean_text)
        or (
            visualization is not None
            and visualization.get("visual_type")
            in {"PROJECT_EXPENSE_SUMMARY", "PROJECT_EXPENSE_BREAKDOWN"}
        )
    )
    if should_refresh_expense_text and visualization:
        narrative = generate_narrative(user_message, visualization, tool_results, language)
        if narrative:
            clean_text = narrative
    elif not clean_text.strip():
        clean_text = generate_narrative(user_message, visualization, tool_results, language)

    for result in reversed(tool_results):
        if isinstance(result, dict) and result.get("quality_warning") and not clean_text.strip():
            clean_text = str(result["quality_warning"])
            break

    if visualization:
        for result in reversed(tool_results):
            if not isinstance(result, dict):
                continue
            date_from = result.get("date_from")
            date_to = result.get("date_to")
            if date_from or date_to:
                visualization = dict(visualization)
                if date_from:
                    visualization["date_from"] = date_from
                if date_to:
                    visualization["date_to"] = date_to
                if result.get("_date_was_defaulted"):
                    visualization["date_was_defaulted"] = True
                break

        visualization = apply_progressive_disclosure(
            visualization,
            user_message,
            tool_results,
        )

    is_quality, issues = validate_response_quality({
        "text": clean_text,
        "visualization": visualization,
    })
    record_quality_result(is_quality)
    if not is_quality:
        logger.warning("[Quality] issues detected: %s", issues)

    return clean_text, visualization


def _grouped_table_to_bar_chart(visualization: dict[str, Any]) -> dict[str, Any] | None:
    groups = (visualization.get("data") or {}).get("groups") or []
    if not groups:
        return None
    labels: list[str] = []
    values: list[float] = []
    for group in groups:
        label = humanize_group_label(group.get("name"))
        numeric = next(
            (
                float(value)
                for value in (group.get("aggregates") or {}).values()
                if isinstance(value, (int, float)) and float(value) > 0
            ),
            0.0,
        )
        if numeric <= 0:
            continue
        labels.append(label)
        values.append(numeric)
    if not labels:
        return None
    rows = [[label, value] for label, value in zip(labels, values)]
    rows.sort(key=lambda item: item[1], reverse=True)
    return {
        "visual_type": "BAR_CHART",
        "label": visualization.get("label") or "Comparison",
        "value": len(rows),
        "unit": visualization.get("unit") or "AED",
        "data": {
            "labels": [row[0] for row in rows],
            "values": [row[1] for row in rows],
            "rows": rows,
            "formatted_values": [format_currency(row[1]) for row in rows],
        },
    }

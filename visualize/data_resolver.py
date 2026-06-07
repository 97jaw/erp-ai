"""Resolve full tabular data from chat visualizations for PDF/Excel export."""

from __future__ import annotations

import json
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def resolve_table_from_visualization(viz: dict[str, Any] | None) -> dict[str, Any]:
    """
    Return {headers, rows, title, visual_type} using all_rows / detail_table when
    summary-level payloads omit visible rows.
    """
    viz = _as_dict(viz)
    if not viz:
        return {"headers": [], "rows": [], "title": None, "visual_type": None}

    data = viz.get("data") if isinstance(viz.get("data"), dict) else {}
    visual_type = str(viz.get("visual_type") or "")
    title = viz.get("label") or viz.get("title") or data.get("report_name")

    if visual_type == "FINANCIAL_REPORT":
        detail = data.get("detail_table") if isinstance(data.get("detail_table"), dict) else {}
        headers = list(
            detail.get("headers")
            or data.get("headers")
            or ["Account", "Debit", "Credit", "Balance"]
        )
        rows = _coerce_rows(
            data.get("all_rows")
            or detail.get("rows")
            or data.get("rows")
            or data.get("accounts")
        )
        return {
            "headers": headers,
            "rows": rows,
            "title": title,
            "visual_type": visual_type,
        }

    if visual_type == "DATA_TABLE":
        detail = data.get("detail_table") if isinstance(data.get("detail_table"), dict) else {}
        headers = list(detail.get("headers") or data.get("headers") or [])
        rows = _coerce_rows(
            data.get("all_rows") or detail.get("rows") or data.get("rows")
        )
        return {
            "headers": headers,
            "rows": rows,
            "title": title,
            "visual_type": visual_type,
        }

    if visual_type == "GROUPED_TABLE":
        headers, rows = _flatten_grouped_table(data)
        return {
            "headers": headers,
            "rows": rows,
            "title": title,
            "visual_type": visual_type,
        }

    headers = list(data.get("headers") or [])
    rows = _coerce_rows(data.get("all_rows") or data.get("rows"))
    if not headers and rows and isinstance(rows[0], dict):
        headers = list(rows[0].keys())
    return {
        "headers": headers,
        "rows": rows,
        "title": title,
        "visual_type": visual_type or None,
    }


def _coerce_rows(raw: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    return [row for row in raw if row is not None]


def _flatten_grouped_table(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    groups = data.get("all_groups") or data.get("groups") or []
    if not isinstance(groups, list):
        return [], []

    flat_rows: list[dict[str, Any]] = []
    headers: list[str] = []

    for group in groups:
        if not isinstance(group, dict):
            continue
        group_label = str(group.get("label") or group.get("name") or "Group")
        group_rows = group.get("rows") or []
        if not isinstance(group_rows, list):
            continue
        for row in group_rows:
            if not isinstance(row, dict):
                continue
            merged = {"Group": group_label, **row}
            flat_rows.append(merged)
            for key in merged:
                if key not in headers:
                    headers.append(key)

    if not headers and flat_rows:
        headers = list(flat_rows[0].keys())
    return headers, flat_rows


def collect_tables_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for item in items:
        viz = _as_dict(item.get("visualization"))
        if not viz:
            continue
        table = resolve_table_from_visualization(viz)
        if table.get("rows"):
            question = (item.get("question") or "").strip()
            table["title"] = table.get("title") or question[:120] or "Data"
            tables.append(table)
    return tables


def enrich_pdf_sections(
    sections: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fill empty table sections (or add tables) from dropped item visualizations."""
    source_tables = collect_tables_from_items(items)
    if not source_tables:
        return sections

    enriched = [dict(section) for section in sections]
    source_index = 0

    for section in enriched:
        if section.get("type") != "table":
            continue
        data = dict(section.get("data") or {})
        rows = data.get("rows") or []
        if rows:
            continue
        if source_index >= len(source_tables):
            break
        source = source_tables[source_index]
        source_index += 1
        data["headers"] = data.get("headers") or source.get("headers") or []
        data["rows"] = source.get("rows") or []
        section["data"] = data
        if not section.get("title"):
            section["title"] = source.get("title") or "Data"

    if source_index < len(source_tables):
        for table in source_tables[source_index:]:
            enriched.append({
                "type": "table",
                "title": table.get("title") or "Data",
                "data": {
                    "headers": table.get("headers") or [],
                    "rows": table.get("rows") or [],
                },
            })

    return enriched

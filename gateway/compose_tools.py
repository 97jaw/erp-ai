from __future__ import annotations

import statistics
from typing import Any


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _run_operation(op: str, values: list[float]) -> float | None:
    if not values:
        return None

    normalized = (op or "").strip().lower()
    if normalized in {"sum", "total"}:
        return round(sum(values), 4)
    if normalized in {"avg", "average", "mean"}:
        return round(statistics.fmean(values), 4)
    if normalized == "median":
        return round(statistics.median(values), 4)
    if normalized == "min":
        return round(min(values), 4)
    if normalized == "max":
        return round(max(values), 4)
    if normalized == "count":
        return float(len(values))
    if normalized in {"percent_change", "change_percent"} and len(values) >= 2:
        previous, current = values[-2], values[-1]
        if previous == 0:
            return None
        return round(((current - previous) / abs(previous)) * 100, 4)
    if normalized == "ratio" and len(values) >= 2:
        denominator = values[1]
        if denominator == 0:
            return None
        return round(values[0] / denominator, 4)
    if normalized == "difference" and len(values) >= 2:
        return round(values[0] - values[1], 4)
    return None


def calculate(tool_input: dict[str, Any]) -> dict[str, Any]:
    operations = tool_input.get("operations") or []
    if not operations:
        return {
            "error": "missing_operations",
            "message": "operations is required for calculate",
        }

    results: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        op = operation.get("op") or operation.get("operation")
        raw_values = operation.get("values") or []
        values = [_to_float(value) for value in raw_values]
        computed = _run_operation(str(op or ""), values)
        results.append({
            "id": operation.get("id") or f"op_{index + 1}",
            "label": operation.get("label"),
            "op": op,
            "values": values,
            "result": computed,
        })

    return {
        "results": results,
        "result_count": len(results),
        "synthesized": True,
    }


def _normalize_row(row: Any, columns: list[str]) -> dict[str, Any]:
    if isinstance(row, dict):
        return {column: row.get(column) for column in columns}
    if isinstance(row, (list, tuple)):
        return {
            columns[index]: row[index]
            for index in range(min(len(columns), len(row)))
        }
    return {columns[0]: row} if columns else {"value": row}


def compose_report(tool_input: dict[str, Any]) -> dict[str, Any]:
    title = (tool_input.get("title") or "Composed Report").strip()
    columns = [str(column) for column in (tool_input.get("columns") or [])]
    rows = tool_input.get("rows") or []
    if not columns and rows:
        first = rows[0]
        if isinstance(first, dict):
            columns = [str(key) for key in first.keys()]

    if not columns:
        return {
            "error": "missing_columns",
            "message": "columns or row dictionaries are required for compose_report",
        }

    normalized_rows: list[dict[str, Any]] = [
        _normalize_row(row, columns)
        for row in rows
    ]

    totals: dict[str, Any] = {}
    for column in columns:
        numeric_values: list[float] = []
        for row in normalized_rows:
            value = row.get(column)
            if value in (None, ""):
                numeric_values = []
                break
            numeric_values.append(_to_float(value))
        if numeric_values:
            totals[column] = round(sum(numeric_values), 4)

    return {
        "title": title,
        "subtitle": tool_input.get("subtitle"),
        "date_range": tool_input.get("date_range"),
        "report_type": tool_input.get("report_type") or "composed",
        "columns": columns,
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "totals": totals,
        "notes": tool_input.get("notes"),
        "synthesized": True,
        "data": {
            "headers": columns,
            "rows": [
                [row.get(column) for column in columns]
                for row in normalized_rows
            ],
        },
    }

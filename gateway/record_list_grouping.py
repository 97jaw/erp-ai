"""Group large list/table visualizations (LPO, PO, invoices) by vendor or user request."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from gateway.quality_intent import detect_query_intent

_GROUP_BY_VENDOR_RE = re.compile(
    r"\b(?:group(?:ed)?\s*by|groupby|per|by)\s+(?:the\s+)?(?:lpo\s+)?vendor\b|"
    r"\bvendor[-\s]?wise\b|"
    r"\b(?:group|breakdown)\s+(?:lpos?|bills?|invoices?)\s+by\s+vendor\b",
    re.I,
)
_GROUP_BY_MONTH_RE = re.compile(
    r"\b(?:group(?:ed)?\s*by|by)\s+month\b|\bmonth[-\s]?wise\b",
    re.I,
)

_DEFAULT_GROUP_THRESHOLD = 6


def _column_index(headers: list[str], *needles: str) -> int | None:
    lowered = [str(header or "").lower() for header in headers]
    for needle in needles:
        token = needle.lower()
        for index, header in enumerate(lowered):
            if token in header:
                return index
    return None


def _parse_amount(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def detect_list_group_field(user_message: str, headers: list[str]) -> str | None:
    """Return grouping dimension: vendor, month, or None."""
    message = user_message or ""
    if _GROUP_BY_VENDOR_RE.search(message):
        return "vendor"
    if _GROUP_BY_MONTH_RE.search(message):
        return "month"
    intent = detect_query_intent(message)
    if intent.get("grouped"):
        if _column_index(headers, "vendor", "partner", "supplier", "client"):
            return "vendor"
        if _column_index(headers, "date"):
            return "month"
    return None


def _group_key_from_row(
    row: list[Any],
    *,
    group_idx: int | None,
    date_idx: int | None,
    group_field: str,
) -> str:
    if group_field == "month" and date_idx is not None:
        raw = str(row[date_idx] or "").strip()
        return raw[:7] if len(raw) >= 7 else raw or "Unknown period"
    if group_idx is not None:
        label = str(row[group_idx] or "").strip()
        return label or "Unassigned"
    return "All"


def build_grouped_table_visual(
    table_visual: dict[str, Any],
    *,
    group_field: str = "vendor",
    include_children: bool = True,
) -> dict[str, Any] | None:
    data = table_visual.get("data") or {}
    headers = list(data.get("headers") or [])
    rows = list(data.get("rows") or [])
    if not headers or not rows:
        return None

    group_idx = _column_index(headers, "vendor", "partner", "supplier", "client")
    amount_idx = _column_index(headers, "total", "amount", "aed")
    label_idx = _column_index(headers, "bill", "invoice", "po", "number", "ref") or 0
    date_idx = _column_index(headers, "date")

    buckets: dict[str, list[list[Any]]] = defaultdict(list)
    for row in rows:
        key = _group_key_from_row(
            row,
            group_idx=group_idx,
            date_idx=date_idx,
            group_field=group_field,
        )
        buckets[key].append(row)

    groups: list[dict[str, Any]] = []
    for name in sorted(buckets, key=lambda item: item.lower()):
        bucket_rows = buckets[name]
        total_amount = sum(
            _parse_amount(row[amount_idx]) if amount_idx is not None else 0.0
            for row in bucket_rows
        )
        node: dict[str, Any] = {
            "name": name,
            "aggregates": {
                "count": len(bucket_rows),
                "total (AED)": round(total_amount, 2),
            },
        }
        if include_children:
            node["children"] = [
                {
                    "name": str(row[label_idx] or "Record"),
                    "aggregates": {
                        "total (AED)": round(
                            _parse_amount(row[amount_idx]) if amount_idx is not None else 0.0,
                            2,
                        ),
                    },
                }
                for row in bucket_rows
            ]
        groups.append(node)

    if not groups:
        return None

    dimension = "Vendor" if group_field == "vendor" else "Month"
    title = str(table_visual.get("label") or "Records")
    if dimension.lower() not in title.lower():
        title = f"{title} — by {dimension}"

    return {
        "visual_type": "GROUPED_TABLE",
        "label": title,
        "value": len(groups),
        "unit": "groups",
        "disclosure_exempt": True,
        "detail_label": title,
        "data": {"groups": groups},
        "data_table": {
            "headers": headers,
            "rows": rows,
        },
    }


def enhance_list_visualization(
    visualization: dict[str, Any] | None,
    user_message: str = "",
) -> dict[str, Any] | None:
    """Convert large DATA_TABLE lists to GROUPED_TABLE when appropriate."""
    if not visualization or visualization.get("visual_type") != "DATA_TABLE":
        return visualization

    headers = list((visualization.get("data") or {}).get("headers") or [])
    rows = list((visualization.get("data") or {}).get("rows") or [])
    if not rows:
        return visualization

    group_field = detect_list_group_field(user_message, headers)
    has_vendor_col = _column_index(headers, "vendor", "partner", "supplier") is not None
    has_date_col = _column_index(headers, "date") is not None
    should_group = bool(group_field) or (
        len(rows) >= _DEFAULT_GROUP_THRESHOLD and (has_vendor_col or has_date_col)
    )
    if not should_group:
        return visualization

    if not group_field:
        group_field = "vendor" if has_vendor_col else "month"

    grouped = build_grouped_table_visual(
        visualization,
        group_field=group_field,
        include_children=True,
    )
    return grouped or visualization

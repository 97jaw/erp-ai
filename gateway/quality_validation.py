from __future__ import annotations

import json
import re
from typing import Any

FORBIDDEN_PATTERNS = (
    ":sum:",
    ":count:",
    ":avg:",
    "__count",
    "__domain",
    "amount_total:",
    "partner_id:",
    "partner_id[",
)

COMPARISON_HINTS = re.compile(r"\bcompar", re.IGNORECASE)
MONEY_HINTS = re.compile(r"\b(revenue|sales|profit|expense|cost|amount|aed)\b", re.IGNORECASE)


def is_suspicious_group_result(result: dict[str, Any]) -> bool:
    groups = result.get("groups") or []
    if not groups:
        return True
    aggregates = result.get("aggregates") or ["id:count"]
    values: list[float] = []
    for group in groups:
        for spec in aggregates:
            key = str(spec)
            raw = group.get(key, group.get(key.split(":")[0], 0))
            try:
                values.append(float(raw or 0))
            except (TypeError, ValueError):
                continue
    return bool(values) and all(value == 0 for value in values)


def validate_response_quality(response: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    text = response.get("text") or ""
    visualization = response.get("visualization") or {}
    viz_str = json.dumps(visualization, default=str)

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in text or pattern in viz_str:
            issues.append(f"Raw field syntax visible: {pattern}")

    visual_type = visualization.get("visual_type")
    data = visualization.get("data") or {}
    values = data.get("values") or []
    if visual_type == "BAR_CHART" and values and all(float(value or 0) == 0 for value in values):
        issues.append("All values are zero — likely wrong query")

    if MONEY_HINTS.search(text) and "AED" not in text and "AED" not in viz_str:
        issues.append("Money mentioned but no currency formatting")

    if COMPARISON_HINTS.search(text) and visual_type not in {"BAR_CHART", "PIVOT_TABLE", "DATA_TABLE"}:
        issues.append("Comparison intent but wrong visualization type")

    if visualization and not text.strip():
        issues.append("Visualization without narrative")

    return len(issues) == 0, issues

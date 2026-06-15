"""Audit-specific helpers for the unified agent handler."""

from __future__ import annotations

import json
from typing import Any

TOOL_RESULT_CHAR_LIMIT = 12000


def summarize_large_result(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    timeline = summary.get("timeline")
    if isinstance(timeline, list) and len(timeline) > 30:
        summary["timeline"] = timeline[:30]
        summary["_timeline_truncated"] = True
    by_model = summary.get("by_model")
    if isinstance(by_model, list):
        trimmed_models = []
        for group in by_model[:15]:
            if not isinstance(group, dict):
                continue
            group_copy = dict(group)
            records = group_copy.get("records")
            if isinstance(records, list) and len(records) > 10:
                group_copy["records"] = records[:10]
                group_copy["_records_truncated"] = True
            trimmed_models.append(group_copy)
        summary["by_model"] = trimmed_models
    records = summary.get("records")
    if isinstance(records, list) and len(records) > 50:
        summary["records"] = records[:50]
        summary["_records_truncated"] = True
    return summary


def audit_visualization_payload(payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best structured payload for the audit UI (timeline vs activity)."""
    trail: dict[str, Any] | None = None
    activity: dict[str, Any] | None = None
    for item in payloads:
        data = item.get("data")
        if not isinstance(data, dict) or data.get("status") != "success":
            continue
        if item.get("tool") == "get_audit_trail":
            trail = data
        elif item.get("tool") == "get_user_activity":
            activity = data
    if trail:
        return {"view": "timeline", **trail}
    if activity:
        return {"view": "activity", **activity}
    return None


def prepare_audit_tool_result(result: Any) -> str:
    if isinstance(result, dict):
        result = summarize_large_result(result)
    result_str = json.dumps(result, default=str)
    if len(result_str) > TOOL_RESULT_CHAR_LIMIT:
        result_str = result_str[:TOOL_RESULT_CHAR_LIMIT] + "..."
    return result_str

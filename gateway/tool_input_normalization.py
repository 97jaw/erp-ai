from __future__ import annotations

import ast
import json
from typing import Any


def _parse_structured_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    if not (
        (text.startswith("[") and text.endswith("]"))
        or (text.startswith("{") and text.endswith("}"))
    ):
        return value

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return value


def _as_list(value: Any) -> list[Any]:
    parsed = _parse_structured_value(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, tuple):
        return list(parsed)
    if isinstance(value, str) and parsed is value:
        return [value]
    return [parsed]


def normalize_search_odoo_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(tool_input)
    if "filters" in normalized:
        normalized["filters"] = _as_list(normalized.get("filters"))
    if "fields" in normalized:
        normalized["fields"] = _as_list(normalized.get("fields"))
    return normalized


def normalize_sql_aggregate_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(tool_input)
    for key in ("filters", "group_by", "aggregates"):
        if key in normalized:
            normalized[key] = _as_list(normalized.get(key))
    if "having" in normalized:
        normalized["having"] = _parse_structured_value(normalized.get("having"))
    return normalized


def normalize_group_aggregate_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(tool_input)
    domain = normalized.get("domain", normalized.get("filters"))
    if domain is not None:
        normalized["domain"] = _as_list(domain)
    for key in ("group_by", "aggregates"):
        if key in normalized:
            normalized[key] = _as_list(normalized.get(key))
    if "having" in normalized:
        normalized["having"] = _parse_structured_value(normalized.get("having"))
    order = normalized.get("order_by") or normalized.get("order")
    if order:
        normalized["order_by"] = order
    return normalized


def normalize_tool_input(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "search_odoo":
        return normalize_search_odoo_input(tool_input)
    if tool_name == "sql_aggregate":
        return normalize_sql_aggregate_input(tool_input)
    if tool_name == "group_and_aggregate":
        return normalize_group_aggregate_input(tool_input)
    return dict(tool_input)

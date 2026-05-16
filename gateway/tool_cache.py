from __future__ import annotations

import hashlib
import json
import time
from typing import Any


CACHE_TTLS: dict[str, int] = {
    "search_odoo": 60,
    "get_project_expenses": 180,
    "get_project_financial_data": 180,
    "get_project_cost_categories": 180,
    "get_top_projects_by_metric": 600,
    "get_projects_with_overrun": 600,
    "get_financial_report": 300,
    "get_period_comparison": 600,
    "get_projects_by_client": 300,
    "get_project_counts_by_client": 300,
    "group_and_aggregate": 300,
    "sql_aggregate": 300,
    "compose_report": 300,
    "calculate": 120,
    "generate_pdf_report": 120,
    "synthesize_pdf": 120,
    "get_general_ledger": 1200,
    "get_trial_balance": 1200,
    "query_accounting": 300,
    "get_partner_ageing": 600,
    "get_partner_ledger": 600,
    "get_projects_summary": 300,
    "get_purchase_orders": 180,
}

DEFAULT_CACHE_TTL = 180


class ToolResultCache:
    """Short-lived in-process cache for expensive Odoo tool calls."""

    _entries: dict[str, tuple[float, Any]] = {}

    @classmethod
    def _ttl(cls, tool_name: str) -> int:
        return CACHE_TTLS.get(tool_name, DEFAULT_CACHE_TTL)

    @classmethod
    def make_key(cls, tool_name: str, tool_input: dict[str, Any]) -> str:
        clean = {
            key: value
            for key, value in (tool_input or {}).items()
            if key not in {"context_hint", "cache_bust"}
        }
        payload = json.dumps(clean, sort_keys=True, default=str)
        return hashlib.md5(f"{tool_name}:{payload}".encode("utf-8")).hexdigest()

    @classmethod
    def get(cls, tool_name: str, tool_input: dict[str, Any]) -> Any | None:
        key = cls.make_key(tool_name, tool_input)
        entry = cls._entries.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            cls._entries.pop(key, None)
            return None
        return value

    @classmethod
    def set(cls, tool_name: str, tool_input: dict[str, Any], value: Any) -> None:
        key = cls.make_key(tool_name, tool_input)
        cls._entries[key] = (time.monotonic() + cls._ttl(tool_name), value)

    @classmethod
    def delete(cls, tool_name: str, tool_input: dict[str, Any]) -> None:
        cls._entries.pop(cls.make_key(tool_name, tool_input), None)

    @classmethod
    def clear(cls) -> None:
        cls._entries.clear()

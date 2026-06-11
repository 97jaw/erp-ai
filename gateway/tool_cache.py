from __future__ import annotations

import hashlib
import time
from typing import Any

CACHE_TTLS: dict[str, int] = {
    "search_odoo": 60,
    "search_entities": 120,
    "get_project_expenses": 180,
    "get_project_financial_data": 180,
    "get_project_cost_categories": 180,
    "get_project_expense_summary": 180,
    "get_project_expense_breakdown": 180,
    "compare_project_expenses": 180,
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
ENTITY_CACHE_TTL_SECONDS = 300

ENTITY_BOUND_TOOLS = frozenset(
    {
        "get_project_expenses",
        "get_project_financial_data",
        "get_project_cost_categories",
        "get_project_expense_summary",
        "get_project_expense_breakdown",
        "compare_project_expenses",
        "get_purchase_orders",
        "get_partner_ageing",
        "get_partner_ledger",
    },
)


def build_tool_cache_key(
    user_id: int | str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    """Build cache key scoped by user and entity identity."""
    payload = dict(tool_input or {})
    entity_id = (
        payload.get("project_id")
        or payload.get("partner_id")
        or payload.get("employee_id")
        or payload.get("id")
    )
    if entity_id is None and payload.get("project_ids"):
        entity_id = ",".join(str(value) for value in sorted(payload["project_ids"]))

    entity_hint = (
        payload.get("project_name")
        or payload.get("name_search")
        or payload.get("query")
        or ""
    )
    hint_hash = (
        hashlib.md5(str(entity_hint).encode("utf-8")).hexdigest()[:8]
        if entity_hint
        else "noent"
    )
    base = f"{user_id}:{tool_name}:{entity_id or 'noid'}:{hint_hash}"

    # Variant discriminators: fields that change WHICH records/metrics are
    # returned for the same entity. Without these, e.g. get_project_records for
    # one project would collide across record_type (invoices vs purchase_orders
    # vs petty_cash) and serve the first cached type for every later query.
    variant_fields = (
        "record_type",
        "move_type",
        "report_type",
        "metric",
        "period",
        "group_by",
        "date_from",
        "date_to",
        "limit",
        "offset",
    )
    variant = {
        field: payload[field]
        for field in variant_fields
        if payload.get(field) is not None
    }
    if not variant:
        return base
    variant_hash = hashlib.md5(
        repr(sorted(variant.items())).encode("utf-8")
    ).hexdigest()[:8]
    return f"{base}:{variant_hash}"


class ToolResultCache:
    """Short-lived in-process cache for expensive Odoo tool calls."""

    _entries: dict[str, tuple[float, Any]] = {}

    @classmethod
    def _ttl(cls, tool_name: str) -> int:
        if tool_name in ENTITY_BOUND_TOOLS:
            return ENTITY_CACHE_TTL_SECONDS
        return CACHE_TTLS.get(tool_name, DEFAULT_CACHE_TTL)

    @classmethod
    def make_key(
        cls,
        tool_name: str,
        tool_input: dict[str, Any],
        user_id: int | str = "anon",
    ) -> str:
        return build_tool_cache_key(user_id, tool_name, tool_input)

    @classmethod
    def get(
        cls,
        tool_name: str,
        tool_input: dict[str, Any],
        user_id: int | str = "anon",
    ) -> Any | None:
        key = cls.make_key(tool_name, tool_input, user_id)
        entry = cls._entries.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            cls._entries.pop(key, None)
            return None
        return value

    @classmethod
    def set(
        cls,
        tool_name: str,
        tool_input: dict[str, Any],
        value: Any,
        user_id: int | str = "anon",
    ) -> None:
        key = cls.make_key(tool_name, tool_input, user_id)
        cls._entries[key] = (time.monotonic() + cls._ttl(tool_name), value)

    @classmethod
    def delete(
        cls,
        tool_name: str,
        tool_input: dict[str, Any],
        user_id: int | str = "anon",
    ) -> None:
        cls._entries.pop(cls.make_key(tool_name, tool_input, user_id), None)

    @classmethod
    def clear(cls) -> None:
        cls._entries.clear()

    @classmethod
    def clear_user(cls, user_id: int | str) -> None:
        """Drop cached tool results for one user (e.g. after topic shift)."""
        prefix = f"{user_id}:"
        cls._entries = {
            key: value for key, value in cls._entries.items() if not key.startswith(prefix)
        }

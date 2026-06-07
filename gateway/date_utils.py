"""Default date range enforcement for financial tool calls (QUERY_RESPONSE_INTELLIGENCE Phase 2)."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RANGE_DAYS = 90

# Tools that accept date_from / date_to and must not run open-ended.
DATE_RANGE_TOOLS = frozenset({
    "query_accounting",
    "get_financial_report",
    "get_general_ledger",
    "get_trial_balance",
    "get_balance_sheet",
    "get_partner_ageing",
    "group_and_aggregate",
    "get_period_comparison",
    "get_top_projects_by_metric",
    "get_projects_with_overrun",
    "get_projects_by_client",
    "get_project_counts_by_client",
    "get_project_cost_categories",
    "get_project_expenses",
    "get_project_financial_data",
    "sql_aggregate",
    "compose_report",
})


def get_default_date_range() -> tuple[str, str]:
    today = date.today()
    date_from = (today - timedelta(days=DEFAULT_RANGE_DAYS)).strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")
    return date_from, date_to


def _normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


def enforce_date_range(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Inject and validate date_from/date_to for financial tools."""
    if tool_name not in DATE_RANGE_TOOLS:
        return tool_input

    enriched = dict(tool_input)
    date_from = _normalize_date(enriched.get("date_from"))
    date_to = _normalize_date(enriched.get("date_to"))
    today_str = date.today().strftime("%Y-%m-%d")

    if not date_from and not date_to:
        date_from, date_to = get_default_date_range()
        enriched["date_from"] = date_from
        enriched["date_to"] = date_to
        enriched["_date_was_defaulted"] = True
        logger.info("[DateRange] Defaulted %s to last %s days: %s → %s", tool_name, DEFAULT_RANGE_DAYS, date_from, date_to)
    elif not date_from and date_to:
        end = date.fromisoformat(date_to)
        enriched["date_from"] = (end - timedelta(days=DEFAULT_RANGE_DAYS)).strftime("%Y-%m-%d")
        enriched["date_to"] = date_to
    elif date_from and not date_to:
        enriched["date_from"] = date_from
        enriched["date_to"] = today_str
    else:
        enriched["date_from"] = date_from
        enriched["date_to"] = date_to

    if enriched["date_from"] > enriched["date_to"]:
        enriched["date_from"], enriched["date_to"] = enriched["date_to"], enriched["date_from"]

    if enriched["date_to"] > today_str:
        enriched["date_to"] = today_str

    return enriched

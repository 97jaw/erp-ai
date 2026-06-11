"""Project expense intelligence tools — wrap project.financial.service mobile APIs."""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

from gateway.core.context_stack import ContextStack

logger = logging.getLogger(__name__)

SERVICE_MODEL = "project.financial.service"
SUMMARY_METHOD = "get_project_expense_summary_mobile"
BREAKDOWN_METHOD = "get_project_expense_breakdown_mobile"
DASHBOARD_METHOD = "get_project_expense_dashboard"

SUMMARY_SOURCE = "project_expense_summary"
SUMMARY_SOURCE_MOBILE = "project_expense_summary_mobile"
SUMMARY_SOURCE_DASHBOARD = "project_expense_dashboard"

SUMMARY_SOURCES = frozenset(
    {
        SUMMARY_SOURCE,
        SUMMARY_SOURCE_MOBILE,
        SUMMARY_SOURCE_DASHBOARD,
    },
)

RANK_FIELD_MAP = {
    "total_expenses": "total_expenses",
    "spend_percent": "spend_percent_of_wo",
    "variance": "variance_amount",
    "wo_amount": "wo_amount",
}

PROJECT_EXPENSE_TOOL_NAMES = frozenset(
    {
        "get_project_expense_summary",
        "get_project_expense_breakdown",
        "compare_project_expenses",
    }
)

PROJECT_EXPENSE_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_project_expense_summary",
        "description": (
            "Get expense summary for a SINGLE project. Returns KPIs (total expenses, "
            "W.O amount, spend %), top 3 trade categories with percentages, and "
            "categorized expense lines (LPO, petty cash, labor, materials, etc.).\n\n"
            "USE THIS WHEN:\n"
            "- User asks for project costs/expenses overview\n"
            "- User wants top spending categories\n"
            "- User asks 'how much did we spend on Project X'\n"
            "- User asks budget vs actual style questions\n\n"
            "DO NOT USE for:\n"
            "- GL account drill-down (use get_project_expense_breakdown)\n"
            "- Multiple projects (use compare_project_expenses)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "Odoo project.project ID. Must be resolved before calling.",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_project_expense_breakdown",
        "description": (
            "Get FULL GL breakdown for a project — hierarchical view of all "
            "expense accounts grouped by Main Group → Sub Group → Account. "
            "Returns the complete expense distribution at GL level.\n\n"
            "USE THIS WHEN:\n"
            "- User asks 'break down by account'\n"
            "- User asks 'show GL details'\n"
            "- User wants to drill into a specific category\n"
            "- User asks 'where did the money go exactly'\n\n"
            "DO NOT USE for:\n"
            "- Summary view (use get_project_expense_summary instead — smaller payload)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "main_group_filter": {
                    "type": "string",
                    "description": "Optional: filter to specific Main Group (MG) code or name",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "compare_project_expenses",
        "description": (
            "Compare expense data across MULTIPLE projects side-by-side. "
            "Returns each project's KPIs, ranks them by spend, and computes variance "
            "between them. Use when user wants to compare 2+ projects.\n\n"
            "USE THIS WHEN:\n"
            "- 'Compare Zayidia Boys School and Zayidia Girls School'\n"
            "- 'Which project is over budget'\n"
            "- 'Top 5 projects by expense'\n"
            "- 'Show me how Project A and B compare'\n\n"
            "DO NOT USE for:\n"
            "- Single project (use get_project_expense_summary)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 10,
                    "description": "List of 2-10 project IDs to compare",
                },
                "rank_by": {
                    "type": "string",
                    "enum": ["total_expenses", "spend_percent", "variance", "wo_amount"],
                    "default": "total_expenses",
                },
            },
            "required": ["project_ids"],
        },
    },
]


async def _call_financial_service(
    adapter: Any,
    method: str,
    project_id: int,
) -> dict[str, Any]:
    """Call project.financial.service via XML-RPC in a worker thread."""
    return await asyncio.to_thread(
        adapter.call_method,
        SERVICE_MODEL,
        method,
        [project_id],
    )


def _service_error(message: str, *, error_code: str = "service_call_failed") -> dict[str, Any]:
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }


def _unwrap_odoo_payload(result: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
    """Accept wrapped {status, data} or raw mobile/dashboard dicts from Odoo."""
    if result.get("status") == "error":
        return "error", None, str(result.get("message") or result.get("error_code") or "error")

    if result.get("status") == "success":
        data = result.get("data")
        if isinstance(data, dict):
            return "success", data, None

    summary_keys = {"total_expenses", "project_count", "top_expenses", "expense_lines"}
    dashboard_keys = {"kpis", "cost_distribution"}
    breakdown_keys = {"breakdown", "wizard_id"}
    if summary_keys & set(result.keys()):
        return "success", result, None
    if dashboard_keys & set(result.keys()):
        return "success", result, None
    if breakdown_keys & set(result.keys()):
        return "success", result, None

    return "unknown", None, "Unexpected response shape from Odoo service"


def _validate_summary_payload(data: dict[str, Any]) -> bool:
    """Require core KPI fields and at least one breakdown dimension."""
    try:
        total_expenses = float(data.get("total_expenses", data.get("total_cost", 0)) or 0)
    except (TypeError, ValueError):
        return False

    wo_raw = data.get("project_count", data.get("wo_amount"))
    if wo_raw is not None:
        try:
            float(wo_raw)
        except (TypeError, ValueError):
            return False

    expense_lines = data.get("expense_lines") or []
    top_expenses = data.get("top_expenses") or []
    if expense_lines or top_expenses:
        return True
    return total_expenses > 0


def _spend_percent(wo_amount: float, total_expenses: float, explicit: Any = None) -> float | None:
    if wo_amount <= 0:
        return None
    if explicit is not None:
        try:
            return float(explicit)
        except (TypeError, ValueError):
            pass
    return round((total_expenses / wo_amount) * 100, 2)


def _interpret_spend_status(
    wo_amount: float,
    total_expenses: float,
) -> tuple[float | None, str, str]:
    """Return spend % (when meaningful), spend_status, and a user-facing status_label."""
    if wo_amount == 0 and total_expenses == 0:
        return None, "no_data", "No expense data recorded"
    if wo_amount == 0 and total_expenses > 0:
        return None, "no_budget_assigned", "Spending recorded, but no W.O budget assigned"
    if total_expenses > wo_amount:
        spend_pct = round((total_expenses / wo_amount) * 100, 1)
        over_amount = total_expenses - wo_amount
        return (
            spend_pct,
            "over_budget",
            f"Over W.O budget by AED {over_amount:,.0f}",
        )
    spend_pct = round((total_expenses / wo_amount) * 100, 1)
    return spend_pct, "on_track", "On track"


def _normalize_summary_from_mobile(project_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Map Odoo mobile payload to canonical AI tool shape."""
    wo_amount = float(data.get("project_count") or data.get("wo_amount") or 0)
    total_expenses = float(data.get("total_expenses") or 0)
    spend_pct, spend_status, status_label = _interpret_spend_status(wo_amount, total_expenses)
    if wo_amount > 0 and data.get("spend_percent_of_wo") is not None:
        spend_pct = _spend_percent(wo_amount, total_expenses, data.get("spend_percent_of_wo"))
    return {
        "status": "success",
        "project_id": project_id,
        "project_name": data.get("project_name") or f"Project {project_id}",
        "agreement_name": data.get("agreement_name"),
        "client_name": data.get("partner_name") or data.get("client_name"),
        "currency": data.get("currency_name") or data.get("currency") or "AED",
        "wo_amount": wo_amount,
        "total_expenses": total_expenses,
        "spend_percent_of_wo": spend_pct,
        "spend_status": spend_status,
        "status_label": status_label,
        "estimation_amount": data.get("estimation_amount"),
        "top_expenses": data.get("top_expenses") or [],
        "expense_lines": data.get("expense_lines") or [],
        "variance_amount": wo_amount - total_expenses,
        "is_over_budget": total_expenses > wo_amount if wo_amount > 0 else False,
        "_source": SUMMARY_SOURCE,
        "_origin": SUMMARY_SOURCE_MOBILE,
    }


def _category_rows_from_distribution(distribution: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for category in distribution:
        name = str(category.get("name") or category.get("category") or "Unknown")
        items = category.get("items") or []
        amount = sum(float(item.get("amount") or 0) for item in items)
        if amount <= 0 and category.get("total") is not None:
            amount = float(category.get("total") or 0)
        if amount > 0:
            rows.append({"name": name, "amount": amount})
    return rows


def _normalize_summary_from_dashboard(project_id: int, dashboard: dict[str, Any]) -> dict[str, Any]:
    """Map expense dashboard KPIs + cost_distribution into mobile summary shape."""
    kpis = dashboard.get("kpis") or {}
    wo_amount = float(kpis.get("budget") or dashboard.get("wo_amount") or 0)
    total_expenses = float(
        kpis.get("total_cost") or kpis.get("total_expense") or dashboard.get("total_expenses") or 0,
    )
    categories = _category_rows_from_distribution(dashboard.get("cost_distribution") or [])
    category_total = sum(float(row["amount"]) for row in categories) or total_expenses
    sorted_categories = sorted(categories, key=lambda row: float(row["amount"]), reverse=True)

    top_expenses: list[dict[str, Any]] = []
    for row in sorted_categories[:3]:
        amount = float(row["amount"])
        percent = round((amount / category_total) * 100, 2) if category_total > 0 else 0.0
        top_expenses.append({"name": row["name"], "amount": amount, "percent": percent})

    expense_lines = [
        {"label": str(row["name"]), "amount": float(row["amount"])}
        for row in sorted_categories
        if float(row["amount"]) > 0
    ]
    spend_pct, spend_status, status_label = _interpret_spend_status(wo_amount, total_expenses)
    if wo_amount > 0 and kpis.get("exceed_percent") is not None:
        spend_pct = _spend_percent(wo_amount, total_expenses, kpis.get("exceed_percent"))

    return {
        "status": "success",
        "project_id": project_id,
        "project_name": dashboard.get("project_name") or f"Project {project_id}",
        "agreement_name": dashboard.get("agreement_name"),
        "client_name": dashboard.get("client_name") or dashboard.get("partner_name"),
        "currency": dashboard.get("currency") or dashboard.get("currency_name") or "AED",
        "wo_amount": wo_amount,
        "total_expenses": total_expenses,
        "spend_percent_of_wo": spend_pct,
        "spend_status": spend_status,
        "status_label": status_label,
        "estimation_amount": dashboard.get("estimation_amount"),
        "top_expenses": top_expenses,
        "expense_lines": expense_lines,
        "variance_amount": wo_amount - total_expenses,
        "is_over_budget": total_expenses > wo_amount if wo_amount > 0 else False,
        "_source": SUMMARY_SOURCE,
        "_origin": SUMMARY_SOURCE_DASHBOARD,
    }


async def _fetch_project_expense_summary(project_id: int, adapter: Any) -> dict[str, Any]:
    """Mobile summary first; dashboard fallback when mobile is missing or invalid."""
    mobile_error: str | None = None

    try:
        mobile_result = await _call_financial_service(adapter, SUMMARY_METHOD, project_id)
    except Exception as exc:
        logger.warning("[ProjectExpense] summary mobile call failed for %s: %s", project_id, exc)
        mobile_error = str(exc)
        mobile_result = None

    if isinstance(mobile_result, dict):
        status, data, error_message = _unwrap_odoo_payload(mobile_result)
        if status == "error":
            message = error_message or mobile_error or "Project expense summary request failed"
            if "not found" in message.lower():
                return {"status": "error", "message": message}
            mobile_error = message
        if status == "success" and isinstance(data, dict) and _validate_summary_payload(data):
            return _normalize_summary_from_mobile(project_id, data)
        mobile_error = error_message or mobile_error

    try:
        dashboard_result = await _call_financial_service(adapter, DASHBOARD_METHOD, project_id)
    except Exception as exc:
        logger.warning("[ProjectExpense] dashboard fallback failed for %s: %s", project_id, exc)
        return _service_error(mobile_error or str(exc))

    if not isinstance(dashboard_result, dict):
        return _service_error(mobile_error or "Unexpected dashboard response type from Odoo service")

    status, data, error_message = _unwrap_odoo_payload(dashboard_result)
    if status == "success" and isinstance(data, dict):
        normalized = _normalize_summary_from_dashboard(project_id, data)
        if _validate_summary_payload(
            {
                **normalized,
                "project_count": normalized.get("wo_amount"),
            },
        ):
            logger.info(
                "[ProjectExpense] Using dashboard fallback for project %s (mobile_error=%r)",
                project_id,
                mobile_error,
            )
            return normalized

    return _service_error(
        mobile_error or error_message or "Could not load project expense summary",
    )


async def execute_get_project_expense_summary(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None,
) -> dict[str, Any]:
    """Wrap project.financial.service mobile summary with dashboard fallback."""
    del context
    project_id = int(tool_input["project_id"])
    return await _fetch_project_expense_summary(project_id, adapter)


def _compute_breakdown_totals(groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    computed_groups = copy.deepcopy(groups)
    grand_total = 0.0
    for group in computed_groups:
        group_total = 0.0
        for subgroup in group.get("subgroups") or []:
            sg_total = sum(
                float(account.get("total") or 0)
                for account in (subgroup.get("accounts") or [])
            )
            subgroup["total"] = sg_total
            group_total += sg_total
        group["total"] = group_total
        grand_total += group_total
    return computed_groups, grand_total


def _filter_main_groups(
    groups: list[dict[str, Any]],
    main_group_filter: str | None,
) -> list[dict[str, Any]]:
    if not main_group_filter:
        return groups
    needle = main_group_filter.strip().lower()
    return [
        group
        for group in groups
        if str(group.get("code") or "").lower() == needle
        or str(group.get("name") or "").lower() == needle
    ]


async def execute_get_project_expense_breakdown(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None,
) -> dict[str, Any]:
    """Wrap project.financial.service.get_project_expense_breakdown_mobile."""
    del context
    project_id = int(tool_input["project_id"])
    mg_filter = tool_input.get("main_group_filter")

    try:
        result = await _call_financial_service(adapter, BREAKDOWN_METHOD, project_id)
    except Exception as exc:
        logger.warning("[ProjectExpense] breakdown call failed for %s: %s", project_id, exc)
        return _service_error(str(exc))

    if not isinstance(result, dict):
        return _service_error("Unexpected response type from Odoo service")

    status, data, error_message = _unwrap_odoo_payload(result)
    if status == "error":
        return _service_error(error_message or "Breakdown request failed")
    if not isinstance(data, dict):
        return _service_error("Missing data payload from Odoo service")

    breakdown = data.get("breakdown") or {}
    raw_groups = breakdown.get("groups") or []
    groups, grand_total = _compute_breakdown_totals(
        _filter_main_groups(raw_groups, mg_filter),
    )

    return {
        "status": "success",
        "project_id": project_id,
        "project_name": breakdown.get("title") or data.get("project_name"),
        "currency": data.get("currency_name", "AED"),
        "groups": groups,
        "grand_total": grand_total,
        "grand_total_display": breakdown.get("total_display"),
        "group_count": breakdown.get("groups_count") or len(groups),
        "wizard_id": data.get("wizard_id"),
        "export_url": data.get("export_url"),
        "_source": "project_expense_breakdown_mobile",
        "_truncated": len(groups) > 10,
    }


async def execute_compare_project_expenses(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None,
) -> dict[str, Any]:
    """Compare expense summaries across multiple projects in parallel."""
    from gateway.core.entity_gate import dedupe_project_ids

    project_ids = dedupe_project_ids([int(pid) for pid in tool_input["project_ids"]])
    if len(project_ids) < 2:
        return {
            "status": "error",
            "error_code": "need_two_projects",
            "message": "Compare requires at least two distinct project IDs",
        }
    rank_by = tool_input.get("rank_by", "total_expenses")
    rank_field = RANK_FIELD_MAP.get(rank_by, "total_expenses")

    tasks = [
        execute_get_project_expense_summary({"project_id": pid}, adapter, context)
        for pid in project_ids
    ]
    summaries = await asyncio.gather(*tasks, return_exceptions=True)

    valid: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for pid, summary in zip(project_ids, summaries):
        if isinstance(summary, Exception):
            failed.append({"project_id": pid, "error": str(summary)})
        elif summary.get("status") != "success":
            failed.append(
                {
                    "project_id": pid,
                    "error": summary.get("message") or summary.get("error_code") or "unknown",
                },
            )
        else:
            valid.append(summary)

    if not valid:
        return {
            "status": "error",
            "error_code": "all_projects_failed",
            "message": "Could not fetch data for any project",
            "failures": failed,
        }

    valid.sort(key=lambda item: float(item.get(rank_field) or 0), reverse=True)

    total_wo = sum(float(item.get("wo_amount") or 0) for item in valid)
    total_expenses = sum(float(item.get("total_expenses") or 0) for item in valid)
    over_budget_count = sum(1 for item in valid if item.get("is_over_budget"))

    return {
        "status": "success",
        "projects": valid,
        "failed": failed,
        "ranking": [
            {
                "rank": index + 1,
                "project_id": item["project_id"],
                "project_name": item.get("project_name"),
                "value": item.get(rank_field),
            }
            for index, item in enumerate(valid)
        ],
        "totals": {
            "combined_wo": total_wo,
            "combined_expenses": total_expenses,
            "combined_variance": total_wo - total_expenses,
            "over_budget_count": over_budget_count,
            "project_count": len(valid),
        },
        "ranked_by": rank_by,
        "_source": "compare_project_expenses",
    }


async def execute_project_expense_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Dispatch to the appropriate project expense tool handler."""
    if tool_name == "get_project_expense_summary":
        return await execute_get_project_expense_summary(tool_input, adapter, context)
    if tool_name == "get_project_expense_breakdown":
        return await execute_get_project_expense_breakdown(tool_input, adapter, context)
    if tool_name == "compare_project_expenses":
        return await execute_compare_project_expenses(tool_input, adapter, context)
    raise ValueError(f"Unknown project expense tool: {tool_name}")


def run_project_expense_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Sync entry point for gateway execute_tool (runs async handlers)."""
    return asyncio.run(
        execute_project_expense_tool(tool_name, tool_input, adapter, context),
    )

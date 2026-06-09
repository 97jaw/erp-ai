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


def _normalize_summary(project_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Map Odoo mobile payload to AI tool shape — numeric fields match Odoo exactly."""
    wo_amount = data["project_count"]
    total_expenses = data["total_expenses"]
    return {
        "status": "success",
        "project_id": project_id,
        "project_name": data["project_name"],
        "agreement_name": data.get("agreement_name"),
        "client_name": data.get("partner_name"),
        "currency": data.get("currency_name", "AED"),
        "wo_amount": wo_amount,
        "total_expenses": total_expenses,
        "spend_percent_of_wo": data["spend_percent_of_wo"],
        "estimation_amount": data.get("estimation_amount"),
        "top_expenses": data["top_expenses"],
        "expense_lines": data["expense_lines"],
        "variance_amount": wo_amount - total_expenses,
        "is_over_budget": total_expenses > wo_amount,
        "_source": "project_expense_summary_mobile",
    }


async def execute_get_project_expense_summary(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None,
) -> dict[str, Any]:
    """Wrap project.financial.service.get_project_expense_summary_mobile."""
    del context
    project_id = int(tool_input["project_id"])

    try:
        result = await _call_financial_service(adapter, SUMMARY_METHOD, project_id)
    except Exception as exc:
        logger.warning("[ProjectExpense] summary call failed for %s: %s", project_id, exc)
        return _service_error(str(exc))

    if not isinstance(result, dict):
        return _service_error("Unexpected response type from Odoo service")

    if result.get("status") != "success":
        return result

    data = result.get("data")
    if not isinstance(data, dict):
        return _service_error("Missing data payload from Odoo service")

    return _normalize_summary(project_id, data)


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

    if result.get("status") != "success":
        return result

    data = result.get("data")
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
        "project_name": data.get("project_name"),
        "currency": data.get("currency_name", "AED"),
        "groups": groups,
        "grand_total": grand_total,
        "group_count": len(groups),
        "wizard_id": data.get("wizard_id"),
        "_source": "project_expense_breakdown_mobile",
        "_truncated": len(groups) > 10,
    }


async def execute_compare_project_expenses(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None,
) -> dict[str, Any]:
    """Compare expense summaries across multiple projects in parallel."""
    project_ids = [int(pid) for pid in tool_input["project_ids"]]
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

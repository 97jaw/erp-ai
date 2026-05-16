from __future__ import annotations

import re
from typing import Any


REFETCH_KEYWORDS = (
    "refresh",
    "reload",
    "fresh",
    "latest",
    "update",
    "current",
    "تحديث",
    "الآن",
    "حالياً",
    "now",
)


def should_bust_cache(user_message: str) -> bool:
    message = (user_message or "").lower()
    return any(keyword in message for keyword in REFETCH_KEYWORDS)


def humanize_tool_error(exc: Exception) -> str:
    name = type(exc).__name__
    if "ProjectAmbiguousError" in name:
        return "Multiple projects match. Please pick one."
    if "ProjectNotFoundError" in name:
        return "No project found with that name. Try the WO reference number."
    if "Timeout" in name:
        return "Odoo server is responding slowly. Try again in a moment."
    return "Could not fetch data. Please try a different query."


def format_tool_exception(exc: Exception) -> dict[str, Any]:
    return {
        "error": True,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "user_message": humanize_tool_error(exc),
        "retry_safe": "Timeout" in type(exc).__name__,
    }


def validate_tool_result(tool_name: str, result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    if tool_name == "group_and_aggregate" and isinstance(result.get("error"), str):
        result.setdefault("user_message", result.get("message"))
        recovery = result.setdefault("recovery", {})
        recovery.setdefault("switch_strategy", True)
        recovery.setdefault("do_not_repeat_same_call", True)
        recovery.setdefault("fallback_tool", "sql_aggregate")

    if result.get("error") is True or isinstance(result.get("error"), str):
        return result

    if tool_name == "get_top_projects_by_metric":
        projects = result.get("projects") or []
        valid = [
            project
            for project in projects
            if float(project.get("revenue", 0) or 0) > 0
            or float(project.get("total_cost", 0) or 0) > 0
            or float(project.get("net_profit", 0) or 0) != 0
        ]
        if not valid:
            return {
                **result,
                "projects": [],
                "warning": "No projects with financial activity found in this period.",
                "suggestion": "Try a wider date range or confirm the project has posted costs.",
            }
        result["projects"] = valid

    if tool_name in {"get_project_expenses", "get_project_financial_data"}:
        kpis = result.get("kpis") or {}
        income = float(kpis.get("total_income", 0) or 0)
        expense = float(kpis.get("total_expense", kpis.get("total_cost", 0)) or 0)
        if income == 0 and expense == 0:
            result["warning"] = (
                "This project has no financial activity in the specified period. "
                "Do not invent numbers."
            )

    if tool_name == "get_project_cost_categories":
        categories = result.get("categories") or []
        if not categories:
            result["warning"] = (
                "No categorized cost breakdown was returned for this project."
            )

    if tool_name == "get_projects_with_overrun":
        projects = result.get("projects") or []
        if not projects:
            result["warning"] = "No projects exceeded the requested budget threshold."

    return result


def extract_project_id_from_text(text: str) -> int | None:
    match = re.search(r'project_id["\s:]+(\d+)', text or "")
    if not match:
        return None
    return int(match.group(1))

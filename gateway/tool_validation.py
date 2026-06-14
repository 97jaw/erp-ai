from __future__ import annotations

import re
from typing import Any

# Field-level recovery hints: when a Fault mentions a bad field,
# suggest a corrected field name so the AI can retry.
_FIELD_HINTS: dict[str, dict[str, str]] = {
    "fleet.vehicle": {
        "partner_id": "Use driver_id (res.partner) or employee_id (hr.employee) — fleet.vehicle has no partner_id",
        "name_id": "Use name (char) — fleet.vehicle.name is a plain char field",
    },
    "project.project": {
        "stage_id": "project.project has no stage_id field — use last_update_status or active",
    },
    "project.task": {
        "stage_id": "Use stage_id only on project.task.type, not on task directly — or filter by state",
    },
}


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


def _parse_fault(exc: Exception) -> tuple[str, str, str | None]:
    """Extract (error_type, details, suggestion) from an xmlrpc Fault or ValueError.

    Returns a 3-tuple safe to pass to the AI orchestrator.
    """
    raw = str(exc)

    # --- Invalid field: "Invalid field 'stage_id' on model 'project.project'" ---
    m = re.search(r"Invalid field ['\"]?(\w+)['\"]? on model ['\"]?([\w.]+)['\"]?", raw)
    if m:
        field, model = m.group(1), m.group(2)
        hint = (_FIELD_HINTS.get(model) or {}).get(field)
        return (
            "invalid_field",
            f"{model} has no field '{field}'",
            hint or f"Check available fields on {model} before retrying",
        )

    # --- Access error ---
    if "access" in raw.lower() and ("denied" in raw.lower() or "error" in raw.lower()):
        return "permission_denied", "Insufficient access rights for that model or record", None

    # --- Generic Odoo fault: strip the Python traceback, keep only the last line ---
    if "Traceback" in raw:
        # The meaningful part is the final non-empty line of the fault string
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        clean = lines[-1] if lines else raw[:200]
        return "odoo_error", clean, "Try a different filter or model"

    # --- ValueError from our own code ---
    if isinstance(exc, ValueError):
        return "value_error", raw[:300], None

    return "tool_error", raw[:300], None


def format_tool_exception(exc: Exception) -> dict[str, Any]:
    error_type, details, suggestion = _parse_fault(exc)
    result: dict[str, Any] = {
        "status": "error",
        "error": True,
        "error_type": error_type,
        "details": details,
        "user_message": humanize_tool_error(exc),
        "retry_safe": "Timeout" in type(exc).__name__,
    }
    if suggestion:
        result["suggestion"] = suggestion
    return result


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
    raw = text or ""
    match = re.search(r'project_id["\s:]+(\d+)', raw, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\bproject\s+#?\s*(\d+)\b", raw, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

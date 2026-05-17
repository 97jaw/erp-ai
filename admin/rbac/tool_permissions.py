from __future__ import annotations

from typing import Any

from admin.auth.principal import CurrentUser

REPORT_TYPE_PERMISSIONS: dict[str, str] = {
    "trial_balance": "reports.trial_balance.view",
    "pandl": "reports.pandl.view",
    "balance_sheet": "reports.balance_sheet.view",
    "general_ledger": "reports.general_ledger.view",
    "partner_ageing": "reports.partner_ageing.view",
    "cost_analysis": "reports.project_costs.view",
}

TOOL_PERMISSIONS: dict[str, str | None] = {
    "query_accounting": None,  # resolved from report_type
    "get_financial_report": None,
    "get_trial_balance": "reports.trial_balance.view",
    "get_partner_ageing": "reports.partner_ageing.view",
    "get_partner_ledger": "reports.general_ledger.view",
    "get_project_expenses": "reports.project_costs.view",
    "get_project_cost_categories": "reports.project_costs.view",
    "generate_pdf_report": "features.pdf_generation",
    "sql_aggregate": "features.advanced_queries",
    "group_and_aggregate": "features.advanced_queries",
}


def permission_for_tool(tool_name: str, tool_input: dict[str, Any] | None = None) -> str | None:
    tool_input = tool_input or {}
    if tool_name in ("query_accounting", "get_financial_report"):
        report_type = tool_input.get("report_type", "pandl")
        return REPORT_TYPE_PERMISSIONS.get(report_type)
    return TOOL_PERMISSIONS.get(tool_name)


def check_tool_allowed(user: CurrentUser, tool_name: str, tool_input: dict[str, Any] | None = None) -> str | None:
    code = permission_for_tool(tool_name, tool_input)
    if code is None:
        return None
    if user.has_permission(code):
        return None
    return f"Missing permission: {code}"

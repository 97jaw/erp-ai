from __future__ import annotations

from typing import Any

from admin.auth.principal import CurrentUser
from admin.rbac.model_permissions import permission_for_model

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
    "get_project_expense_summary": "reports.project_costs.view",
    "get_project_expense_breakdown": "reports.project_costs.view",
    "compare_project_expenses": "reports.project_costs.view",
    "get_projects_summary": "odoo.projects.access",
    "get_top_projects_by_metric": "odoo.projects.access",
    "get_projects_with_overrun": "odoo.projects.access",
    "get_projects_by_client": "odoo.projects.access",
    "get_project_counts_by_client": "odoo.projects.access",
    "get_purchase_orders": "odoo.procurement.access",
    "get_my_payslips": "odoo.payroll.access",
    "get_employee_payslips": "odoo.payroll.access",
    "list_recent_payslips": "odoo.payroll.access",
    "generate_pdf_report": "features.pdf_generation",
    "sql_aggregate": "features.advanced_queries",
    "group_and_aggregate": "features.advanced_queries",
    "search_odoo": None,  # resolved from model
    "sql_aggregate_model": None,  # resolved from model
}


def _model_from_tool_input(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    model = tool_input.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def permission_for_tool(tool_name: str, tool_input: dict[str, Any] | None = None) -> str | None:
    tool_input = tool_input or {}
    if tool_name in ("query_accounting", "get_financial_report"):
        report_type = tool_input.get("report_type", "pandl")
        return REPORT_TYPE_PERMISSIONS.get(report_type)
    if tool_name in (
        "search_odoo",
        "group_and_aggregate",
        "sql_aggregate",
        "query_odoo",
        "aggregate_odoo",
    ):
        return permission_for_model(_model_from_tool_input(tool_name, tool_input))
    if tool_name == "introspect_odoo_schema":
        model = _model_from_tool_input(tool_name, tool_input)
        if model:
            return permission_for_model(model)
        return "odoo.full_access"
    return TOOL_PERMISSIONS.get(tool_name)


def _has_payroll_or_hr_access(user: CurrentUser) -> bool:
    return user.has_permission("odoo.payroll.access") or user.has_permission("odoo.hr.access")


def check_tool_allowed(user: CurrentUser, tool_name: str, tool_input: dict[str, Any] | None = None) -> str | None:
    if user.is_super_admin or user.has_permission("odoo.full_access"):
        return None

    if tool_name in ("get_my_payslips", "get_employee_payslips", "list_recent_payslips"):
        if _has_payroll_or_hr_access(user):
            return None
        return "Missing permission: odoo.payroll.access or odoo.hr.access"

    code = permission_for_tool(tool_name, tool_input)
    if code is None:
        return None
    if user.has_permission(code):
        return None

    model = (_model_from_tool_input(tool_name, tool_input) or "").lower()
    if code == "odoo.payroll.access" and model.startswith("hr.payslip") and user.has_permission("odoo.hr.access"):
        return None

    return f"Missing permission: {code}"

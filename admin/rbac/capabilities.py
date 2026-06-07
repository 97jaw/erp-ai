"""Human-readable Odoo capability hints for the agent system prompt."""

from __future__ import annotations

from admin.auth.principal import CurrentUser

_ODOO_PERM_HINTS: dict[str, str] = {
    "odoo.full_access": "all Odoo modules",
    "odoo.projects.access": "projects & tasks (project.project, project.task)",
    "odoo.timesheets.access": "timesheets (account.analytic.line, timesheet models)",
    "odoo.hr.access": "HR (hr.employee, hr.leave, hr.contract, hr.department)",
    "odoo.payroll.access": "payroll & payslips (hr.payslip, hr.payslip.run)",
    "odoo.accounting.access": "accounting (account.move, account.move.line)",
    "odoo.procurement.access": "purchase orders (purchase.order)",
    "odoo.sales.access": "sales (sale.order)",
    "odoo.inventory.access": "inventory (stock.picking, stock.quant)",
    "odoo.crm.access": "CRM & partners (crm.lead, res.partner)",
    "odoo.manufacturing.access": "manufacturing (mrp.production)",
    "odoo.maintenance.access": "maintenance (maintenance.request)",
}


def build_odoo_capabilities_prompt(user: CurrentUser) -> str:
    if user.is_super_admin or user.has_permission("odoo.full_access"):
        return (
            "\n## Odoo data access (granted)\n"
            "You may use search_odoo and group_and_aggregate on any Odoo model, including:\n"
            "- HR: hr.employee, hr.leave, hr.contract\n"
            "- Payroll: hr.payslip, hr.payslip.run\n"
            "- Projects & tasks: project.project, project.task\n"
            "- Timesheets: account.analytic.line (filter by user/project as needed)\n"
            "- Accounting, sales, purchase, inventory, CRM\n"
            "For pending tasks, search project.task with domain for the current user "
            "(e.g. user_ids or personal stage) unless the user names a project.\n"
            "For payslip questions: **get_my_payslips** (self), **get_employee_payslips** "
            "(by File ID / emp_id), or **list_recent_payslips** ('any payslip' / HR browse). "
            "Do not use search_odoo on hr.payslip alone.\n"
            "Never refuse HR/payroll/task questions without calling a tool first.\n"
            "List/search tools return `_query_meta` with total_matching and truncated — "
            "always tell the user when more rows exist in Odoo than were returned.\n"
            "Super admin searches default to up to 2000 rows per tool call (paginated), not 20.\n"
        )

    odoo_codes = sorted(c for c in user.permissions if c.startswith("odoo."))
    if not odoo_codes:
        return (
            "\n## Odoo data access (limited)\n"
            "Financial reports and dedicated project/purchase tools only. "
            "For HR, payroll, or personal tasks, the user lacks odoo.* permissions — "
            "say they need an administrator to grant Odoo module access in Admin → Roles.\n"
        )

    lines = [_ODOO_PERM_HINTS.get(code, code) for code in odoo_codes]
    return (
            "\n## Odoo data access (granted)\n"
            "You may use search_odoo / group_and_aggregate for:\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\nFor personal payslip questions, use get_my_payslips.\n"
            + "Never refuse these modules without trying a tool first.\n"
    )

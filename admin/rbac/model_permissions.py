"""Map Odoo model names to RBAC permission codes."""

from __future__ import annotations

# Longest / most specific prefixes first.
MODEL_PERMISSION_RULES: tuple[tuple[str, str], ...] = (
    ("hr.payslip", "odoo.payroll.access"),
    ("hr.payroll", "odoo.payroll.access"),
    ("hr.salary", "odoo.payroll.access"),
    ("hr.expense.sheet", "odoo.payroll.access"),
    ("hr.leave", "odoo.hr.access"),
    ("hr.contract", "odoo.hr.access"),
    ("hr.employee", "odoo.hr.access"),
    ("hr.department", "odoo.hr.access"),
    ("hr.", "odoo.hr.access"),
    ("account.analytic.line", "odoo.timesheets.access"),
    ("timesheet", "odoo.timesheets.access"),
    ("project.task", "odoo.projects.access"),
    ("project.project", "odoo.projects.access"),
    ("project.", "odoo.projects.access"),
    ("mrp.", "odoo.manufacturing.access"),
    ("maintenance.", "odoo.maintenance.access"),
    ("purchase.", "odoo.procurement.access"),
    ("sale.", "odoo.sales.access"),
    ("stock.", "odoo.inventory.access"),
    ("crm.", "odoo.crm.access"),
    ("account.", "odoo.accounting.access"),
    ("res.partner", "odoo.crm.access"),
)


def permission_for_model(model: str | None) -> str | None:
    """Return required permission code for an Odoo model, or None if unrestricted."""
    if not model:
        return None
    normalized = model.strip().lower()
    for prefix, code in MODEL_PERMISSION_RULES:
        if normalized == prefix or normalized.startswith(prefix):
            return code
    return None

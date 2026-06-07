"""
HR identity: File ID maps to hr.employee (emp_id / employee code), not only res.users.login.

- "My …" tools always resolve the signed-in user's File ID → employee record.
- Admins (with permission) may query other employees by File ID / emp_id.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from admin.auth.principal import CurrentUser
from adapters.v14.connector import OdooV14Adapter

logger = logging.getLogger(__name__)

_EMPLOYEE_READ_FIELDS = (
    "id",
    "name",
    "user_id",
    "emp_id",
    "employee_code",
    "barcode",
    "identification_id",
    "department_id",
    "job_id",
    "work_email",
)


def normalize_employee_file_id(file_id: str | None) -> str:
    """Strip spaces — login File ID ' 2721 ' must match emp_id 2721."""
    return re.sub(r"\s+", "", (file_id or "").strip())


def employee_id_field_names() -> list[str]:
    raw = os.environ.get(
        "ODOO_EMPLOYEE_ID_FIELDS",
        "emp_id,employee_code,barcode,identification_id,pin,registration_number",
    )
    return [name.strip() for name in raw.split(",") if name.strip()]


def discover_employee_identifier_fields(adapter: OdooV14Adapter) -> list[str]:
    """Configured fields plus Odoo fields that look like employee / File ID keys."""
    available = _employee_fields_available(adapter)
    ordered: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        if name and name in available and name not in seen:
            seen.add(name)
            ordered.append(name)

    for name in employee_id_field_names():
        add(name)

    for name, meta in available.items():
        lowered = name.lower()
        label = (meta.get("string") or "").lower()
        hints = (
            "emp_id",
            "employee_code",
            "employee id",
            "file id",
            "badge",
            "identification",
            "registration",
            "staff_id",
            "personnel",
        )
        if any(h in lowered or h in label for h in hints):
            add(name)

    return ordered


def _employee_fields_available(adapter: OdooV14Adapter) -> dict[str, dict[str, Any]]:
    return adapter._get_model_fields("hr.employee")


def _read_fields(adapter: OdooV14Adapter) -> list[str]:
    available = _employee_fields_available(adapter)
    return [f for f in _EMPLOYEE_READ_FIELDS if f in available or f in ("id", "name")]


def resolve_employee_by_file_id(
    adapter: OdooV14Adapter,
    file_id: str,
    *,
    odoo_user_id: int | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve hr.employee from OOA File ID (primary key = emp_id on Elrace)."""
    normalized = normalize_employee_file_id(file_id)
    if not normalized and not odoo_user_id:
        return None, None

    read_fields = _read_fields(adapter)
    available = _employee_fields_available(adapter)
    id_fields = discover_employee_identifier_fields(adapter)

    def _search(
        strategy: str,
        domain: list[list[Any]],
        *,
        require_active: bool,
    ) -> tuple[dict[str, Any] | None, str | None]:
        search_domain = list(domain)
        if require_active and "active" in available:
            search_domain = ["&", *domain, ["active", "=", True]]
        try:
            rows = adapter.search_read(
                model="hr.employee",
                domain=search_domain,
                fields=read_fields,
                limit=5,
            )
        except Exception as exc:
            logger.warning("[HR] employee lookup %s failed: %s", strategy, exc)
            return None, None
        if len(rows) >= 1:
            suffix = "" if len(rows) == 1 else "_first_of_many"
            inactive = (
                f"{strategy}_inactive"
                if not require_active and "active" in available
                else strategy
            )
            return rows[0], f"{inactive}{suffix}"
        return None, None

    # Build strategies using discovered identifier fields
    strategies: list[tuple[str, list[list[Any]]]] = []
    if normalized:
        for field in id_fields:
            strategies.append((field, [[field, "=", normalized]]))
            strategies.append((f"{field}_ilike", [[field, "ilike", normalized]]))
            if normalized.isdigit():
                strategies.append((f"{field}_int", [[field, "=", int(normalized)]]))
                strategies.append((f"{field}_str", [[field, "=", str(int(normalized))]]))
    if odoo_user_id:
        strategies.append(("user_id", [["user_id", "=", odoo_user_id]]))

    for strategy, domain in strategies:
        employee, match = _search(strategy, domain, require_active=True)
        if employee:
            return employee, match

    for strategy, domain in strategies:
        employee, match = _search(strategy, domain, require_active=False)
        if employee:
            return employee, match

    return None, None


def can_query_other_employees(user: CurrentUser) -> bool:
    return (
        user.is_super_admin
        or user.has_permission("odoo.full_access")
        or user.has_permission("data.all_projects")
        or user.has_permission("admin.users.view")
    )


def can_access_employee_file_id(user: CurrentUser, target_file_id: str) -> bool:
    """Self always allowed; others require elevated Odoo/HR access."""
    self_id = normalize_employee_file_id(user.file_id)
    target = normalize_employee_file_id(target_file_id)
    if not target:
        return False
    if self_id and self_id == target:
        return True
    return can_query_other_employees(user)


def resolve_target_employee(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """
    Resolve employee for a tool call.
    Returns (employee, strategy, error_message).
    """
    target_file = employee_file_id or user.file_id or ""
    if not normalize_employee_file_id(target_file):
        return None, None, "employee_file_id or user File ID is required"

    if not can_access_employee_file_id(user, target_file):
        return (
            None,
            None,
            "You may only view your own HR records. Other employees require admin or full Odoo access.",
        )

    employee, strategy = resolve_employee_by_file_id(adapter, target_file)
    if not employee:
        return (
            None,
            None,
            f"No hr.employee found for File ID / emp_id '{normalize_employee_file_id(target_file)}'.",
        )
    return employee, strategy, None


def apply_personal_hr_scope(
    tool_name: str,
    tool_input: dict[str, Any],
    user: CurrentUser,
    adapter: OdooV14Adapter,
) -> dict[str, Any]:
    """
    Auto-scope HR model queries to the signed-in employee when the tool marks _scope_self.
    Injects employee_id into search_odoo / group_and_aggregate for hr.* models.
    """
    scoped = dict(tool_input)
    if not scoped.get("_scope_self"):
        return scoped

    employee, _, err = resolve_target_employee(adapter, user)
    if err or not employee:
        model = (scoped.get("model") or "").strip()
        if model == "hr.payslip" and can_query_other_employees(user):
            scoped.pop("_scope_self", None)
            scoped["_hr_scope_warning"] = (
                "Could not resolve your employee from File ID; searching payslips without self-scope."
            )
            return scoped
        scoped["_hr_scope_error"] = err or "Could not resolve your employee record from File ID."
        return scoped

    employee_id = int(employee["id"])
    scoped["_resolved_employee_id"] = employee_id
    scoped["_resolved_file_id"] = normalize_employee_file_id(user.file_id)

    model = (scoped.get("model") or "").strip()
    if tool_name == "search_odoo" and model.startswith("hr."):
        filters = list(scoped.get("filters") or [])
        if not _domain_mentions_employee(filters):
            field = "employee_id"
            if model == "hr.employee":
                filters = [["id", "=", employee_id]]
            else:
                filters = ["&", ["employee_id", "=", employee_id], *filters] if filters else [
                    ["employee_id", "=", employee_id],
                ]
            scoped["filters"] = filters

    if tool_name == "group_and_aggregate" and (scoped.get("model") or "").startswith("hr."):
        domain = list(scoped.get("domain") or scoped.get("filters") or [])
        if not _domain_mentions_employee(domain):
            scoped["domain"] = ["&", ["employee_id", "=", employee_id], *domain] if domain else [
                ["employee_id", "=", employee_id],
            ]

    return scoped


def _domain_mentions_employee(domain: list[Any]) -> bool:
    text = str(domain).lower()
    return "employee_id" in text or "emp_id" in text


async def build_hr_identity_prompt(user: CurrentUser, adapter: OdooV14Adapter) -> str:
    file_id = normalize_employee_file_id(user.file_id)
    employee, strategy = resolve_employee_by_file_id(adapter, file_id or user.file_id or "")
    others = can_query_other_employees(user)

    lines = [
        "\n## HR identity (File ID = emp_id)",
        f"- Signed-in File ID: {file_id or user.file_id}",
        "- In Elrace Odoo, File ID is the employee key (emp_id / employee code), not necessarily res.users login.",
    ]
    if employee:
        emp_code = None
        for key in employee_id_field_names():
            if employee.get(key):
                emp_code = employee.get(key)
                break
        lines.append(
            f"- Your employee: {employee.get('name')} (hr.employee id {employee['id']}, "
            f"matched via {strategy}"
            + (f", emp_id={emp_code}" if emp_code else "")
            + ")"
        )
        lines.append(
            "- For **payslip** / **salary**: get_my_payslips, get_employee_payslips(employee_file_id=…), "
            "or list_recent_payslips for 'any payslip'. For **my tasks/leave**: search_odoo with _scope_self: true."
        )
    else:
        lines.append(
            f"- No hr.employee with emp_id / employee_code = '{file_id}'. "
            "HR must set emp_id on the employee record to the File ID."
        )

    if others:
        lines.append(
            "- You may query **other employees** by File ID (emp_id) using search_odoo or "
            "get_employee_payslips(employee_file_id=...) per your role permissions."
        )
    else:
        lines.append(
            "- You may only access **your own** HR/payroll records unless granted broader Odoo access."
        )
    return "\n".join(lines) + "\n"

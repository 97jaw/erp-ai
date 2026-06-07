from __future__ import annotations

from typing import Any

from admin.auth.principal import CurrentUser


def apply_data_scope(tool_input: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    """
    Restrict accounting tool inputs when user lacks data.all_projects.
    Injects department_ids for downstream SQL/Odoo filters when applicable.
    """
    if (
        user.is_super_admin
        or user.has_permission("data.all_projects")
        or user.has_permission("odoo.full_access")
    ):
        return tool_input

    scoped = dict(tool_input)
    if user.has_permission("data.own_department_only") and user.department_ids:
        existing = list(scoped.get("department_ids") or [])
        allowed = set(user.department_ids)
        if existing:
            scoped["department_ids"] = [d for d in existing if d in allowed]
        else:
            scoped["department_ids"] = list(user.department_ids)
        scoped["_rbac_department_scoped"] = True
    elif not user.has_permission("data.financial_full"):
        scoped["_rbac_limited_financial"] = True
    return scoped

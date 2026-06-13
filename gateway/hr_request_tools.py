"""Employee request tools — employee.request workflow reads with person/type/date filters."""

from __future__ import annotations

import logging
from typing import Any

from admin.auth.principal import CurrentUser
from adapters.v14.connector import OdooV14Adapter
from gateway.core.hr_payroll_composer import build_employee_name_domain
from gateway.hr_identity import (
    can_access_employee_file_id,
    normalize_employee_file_id,
    resolve_employee_by_file_id,
)

logger = logging.getLogger(__name__)

_REQUEST_FIELDS = (
    "name",
    "employee_id",
    "request_type_id",
    "request_type",
    "status",
    "is_approve",
    "create_date",
    "write_date",
)


def _search_employees_by_name(
    adapter: OdooV14Adapter,
    name_hint: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    parts = [part for part in name_hint.split() if len(part) > 1]
    if not parts:
        return []
    domain: list[Any] = [["active", "=", True], ["name", "ilike", parts[0]]]
    if len(parts) > 1:
        domain.append(["name", "ilike", parts[-1]])
    try:
        return adapter.search_read(
            model="hr.employee",
            domain=domain,
            fields=["id", "name", "emp_id", "department_id"],
            limit=limit,
            order="name asc",
        )
    except Exception as exc:
        logger.warning("[HR] employee name search failed: %s", exc)
        return []


def _present_request(row: dict[str, Any]) -> dict[str, Any]:
    employee = row.get("employee_id")
    employee_name = (
        employee[1] if isinstance(employee, (list, tuple)) and len(employee) > 1 else employee
    )
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "employee_name": employee_name,
        "request_type": row.get("request_type"),
        "status": row.get("status"),
        "is_approve": row.get("is_approve"),
        "create_date": row.get("create_date"),
    }


async def list_employee_requests(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str | None = None,
    employee_name: str | None = None,
    request_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List employee.request rows with optional employee, type, and date filters."""
    limit = min(max(int(limit or 50), 1), 100)
    domain: list[Any] = []
    employee_id: int | None = None
    resolved_name = employee_name

    if employee_file_id:
        target = normalize_employee_file_id(employee_file_id)
        if not can_access_employee_file_id(user, target):
            return {
                "requests": [],
                "count": 0,
                "note": "You may only view your own HR records without admin Odoo access.",
                "_source": "list_employee_requests",
            }
        employee, _ = resolve_employee_by_file_id(adapter, target)
        if employee:
            employee_id = int(employee["id"])
            resolved_name = str(employee.get("name") or resolved_name or "")
        else:
            return {
                "requests": [],
                "count": 0,
                "employee_file_id": target,
                "employee_name": employee_name,
                "note": f"No employee found for file ID {target}.",
                "_source": "list_employee_requests",
            }

    if employee_id is None and employee_name:
        matches = _search_employees_by_name(adapter, employee_name, limit=5)
        if len(matches) == 1:
            employee_id = int(matches[0]["id"])
            resolved_name = str(matches[0].get("name") or employee_name)
        elif len(matches) > 1:
            return {
                "requests": [],
                "count": 0,
                "employee_name": employee_name,
                "ambiguous_employees": [
                    {
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "emp_id": row.get("emp_id"),
                        "department": (
                            row.get("department_id")[1]
                            if isinstance(row.get("department_id"), (list, tuple))
                            and len(row.get("department_id")) > 1
                            else None
                        ),
                    }
                    for row in matches
                ],
                "note": f"Multiple employees match '{employee_name}'. Please specify file ID or full name.",
                "_source": "list_employee_requests",
            }

    if employee_id is not None:
        domain.append(["employee_id", "=", employee_id])
    elif employee_name:
        domain.extend(build_employee_name_domain(employee_name))

    if request_type:
        domain.append(["request_type", "ilike", request_type])
    if date_from:
        domain.append(["create_date", ">=", date_from])
    if date_to:
        domain.append(["create_date", "<=", date_to])
    if status == "pending":
        domain.append(["is_approve", "=", False])
    elif status == "approved":
        domain.append(["is_approve", "=", True])

    try:
        rows = adapter.search_read(
            model="employee.request",
            domain=domain,
            fields=list(_REQUEST_FIELDS),
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        logger.warning("[HR] employee.request query failed: %s", exc)
        return {
            "requests": [],
            "count": 0,
            "note": f"Could not read employee requests: {exc}",
            "_source": "list_employee_requests",
        }

    requests = [_present_request(row) for row in rows]
    return {
        "requests": requests,
        "count": len(requests),
        "employee_id": employee_id,
        "employee_name": resolved_name,
        "employee_file_id": normalize_employee_file_id(employee_file_id) if employee_file_id else None,
        "request_type": request_type,
        "date_from": date_from,
        "date_to": date_to,
        "note": (
            f"No HR requests found for **{resolved_name}** in the selected period."
            if resolved_name and not requests
            else (
                "No HR requests found matching that criteria."
                if not requests
                else None
            )
        ),
        "_source": "list_employee_requests",
    }

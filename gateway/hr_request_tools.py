"""Employee request tools — employee.requests workflow reads with person/type/date filters."""

from __future__ import annotations

import logging
import re
from typing import Any

from admin.auth.principal import CurrentUser
from adapters.v14.connector import OdooV14Adapter
from gateway.core.hr_payroll_composer import (
    EMPLOYEE_REQUESTS_MODEL,
    build_employee_name_domain,
    extract_request_reference,
)
from gateway.hr_identity import (
    can_access_employee_file_id,
    normalize_employee_file_id,
    resolve_employee_by_file_id,
)

logger = logging.getLogger(__name__)

_VALIDATION_MODEL_CANDIDATES = (
    "request.validation.status",
    "request.validation",
)
_REQUEST_FIELD_CANDIDATES = (
    "name",
    "employee_id",
    "request_type_id",
    "status",
    "is_approve",
    "create_date",
    "write_date",
    "date_from",
    "date_to",
    "number_of_days",
    "leave_days",
    "days",
    "first_approver_id",
    "second_approver_id",
    "request_approvals_ids",
    "reason",
    "description",
    "notes",
)
_VALIDATION_FIELD_CANDIDATES = (
    "name",
    "status",
    "user_id",
    "date",
    "write_date",
    "sequence",
    "state",
    "approval_status",
    "approver_id",
    "request_id",
)


def _request_fields(adapter: OdooV14Adapter) -> list[str]:
    available = adapter._get_model_fields(EMPLOYEE_REQUESTS_MODEL) or {}
    if not available:
        return list(_REQUEST_FIELD_CANDIDATES[:8])
    return [field for field in _REQUEST_FIELD_CANDIDATES if field in available]


def _validation_model(adapter: OdooV14Adapter) -> str | None:
    for model in _VALIDATION_MODEL_CANDIDATES:
        if adapter._get_model_fields(model):
            return model
    return None


def _validation_fields(adapter: OdooV14Adapter, model: str) -> list[str]:
    available = adapter._get_model_fields(model) or {}
    return [field for field in _VALIDATION_FIELD_CANDIDATES if field in available]


def _many2one_label(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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


def _leave_duration(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("date_from", "date_to", "number_of_days", "leave_days", "days"):
        if row.get(key) not in (None, "", False):
            out[key if key != "days" else "leave_days"] = row.get(key)
    if out.get("date_from") and out.get("date_to"):
        out["leave_period"] = f"{out['date_from']} to {out['date_to']}"
    return out


def _present_request(row: dict[str, Any], *, include_leave: bool = True) -> dict[str, Any]:
    employee = row.get("employee_id")
    employee_name = _many2one_label(employee)
    request_type = row.get("request_type_id")
    request_type_label = _many2one_label(request_type)
    payload: dict[str, Any] = {
        "id": row.get("id"),
        "name": row.get("name"),
        "employee_name": employee_name,
        "request_type": request_type_label,
        "request_type_id": request_type,
        "status": row.get("status"),
        "is_approve": row.get("is_approve"),
        "create_date": row.get("create_date"),
        "first_approver": _many2one_label(row.get("first_approver_id")),
        "second_approver": _many2one_label(row.get("second_approver_id")),
    }
    if include_leave:
        payload.update(_leave_duration(row))
    return payload


def _present_validation(row: dict[str, Any]) -> dict[str, Any]:
    approver = row.get("user_id") or row.get("approver_id")
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "status": row.get("status") or row.get("approval_status") or row.get("state"),
        "approver": _many2one_label(approver),
        "date": row.get("date") or row.get("write_date"),
        "sequence": row.get("sequence"),
    }


def _fetch_validation_chain(
    adapter: OdooV14Adapter,
    approval_ids: Any,
) -> list[dict[str, Any]]:
    model = _validation_model(adapter)
    if not model or not approval_ids:
        return []
    ids = approval_ids if isinstance(approval_ids, list) else [approval_ids]
    try:
        rows = adapter.search_read(
            model=model,
            domain=[["id", "in", ids]],
            fields=_validation_fields(adapter, model),
            limit=50,
            order="sequence asc, id asc",
        )
    except Exception as exc:
        logger.warning("[HR] validation status read failed: %s", exc)
        return []
    return [_present_validation(row) for row in rows]


def _resolve_employee_scope(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str | None,
    employee_name: str | None,
) -> tuple[int | None, str | None, dict[str, Any] | None]:
    """Return (employee_id, resolved_name, error_payload)."""
    resolved_name = employee_name
    if employee_file_id:
        target = normalize_employee_file_id(employee_file_id)
        if not can_access_employee_file_id(user, target):
            return None, resolved_name, {
                "note": "You may only view your own HR records without admin Odoo access.",
            }
        employee, _ = resolve_employee_by_file_id(adapter, target)
        if employee:
            return int(employee["id"]), str(employee.get("name") or resolved_name or ""), None
        return None, resolved_name, {"note": f"No employee found for file ID {target}."}

    if employee_name:
        matches = _search_employees_by_name(adapter, employee_name, limit=5)
        if len(matches) == 1:
            return int(matches[0]["id"]), str(matches[0].get("name") or employee_name), None
        if len(matches) > 1:
            return None, employee_name, {
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
            }
    return None, resolved_name, None


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
    """List employee.requests rows with optional employee, type, and date filters."""
    limit = min(max(int(limit or 50), 1), 100)
    domain: list[Any] = []
    employee_id, resolved_name, error = _resolve_employee_scope(
        adapter,
        user,
        employee_file_id=employee_file_id,
        employee_name=employee_name,
    )
    if error:
        return {
            "requests": [],
            "count": 0,
            "employee_name": employee_name,
            **error,
            "_source": "list_employee_requests",
        }

    if employee_id is not None:
        domain.append(["employee_id", "=", employee_id])
    elif employee_name:
        domain.extend(build_employee_name_domain(employee_name))

    if request_type:
        domain.append(["request_type_id.name", "ilike", request_type])
    if date_from:
        domain.append(["create_date", ">=", date_from])
    if date_to:
        domain.append(["create_date", "<=", f"{date_to} 23:59:59"])
    if status == "pending":
        domain.append(["is_approve", "=", False])
    elif status == "approved":
        domain.append(["is_approve", "=", True])

    try:
        rows = adapter.search_read(
            model=EMPLOYEE_REQUESTS_MODEL,
            domain=domain,
            fields=_request_fields(adapter),
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        logger.warning("[HR] employee.requests query failed: %s", exc)
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
        "recent_request_ids": [row.get("id") for row in requests[:5] if row.get("id")],
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


async def get_employee_request_detail(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    request_id: int | None = None,
    request_name: str | None = None,
    employee_file_id: str | None = None,
    employee_name: str | None = None,
) -> dict[str, Any]:
    """Fetch one employee.requests row with validation chain and leave dates."""
    domain: list[Any] = []
    if request_id is not None:
        domain.append(["id", "=", int(request_id)])
    elif request_name:
        domain.append(["name", "ilike", request_name.strip()])
    else:
        return {
            "request": None,
            "validation_chain": [],
            "note": "Please specify a request ID or reference to show request details.",
            "_source": "get_employee_request_detail",
        }

    employee_id, resolved_name, error = _resolve_employee_scope(
        adapter,
        user,
        employee_file_id=employee_file_id,
        employee_name=employee_name,
    )
    if error:
        return {
            "request": None,
            "validation_chain": [],
            "employee_name": employee_name,
            **error,
            "_source": "get_employee_request_detail",
        }
    if employee_id is not None:
        domain.append(["employee_id", "=", employee_id])

    try:
        rows = adapter.search_read(
            model=EMPLOYEE_REQUESTS_MODEL,
            domain=domain,
            fields=_request_fields(adapter),
            limit=1,
            order="create_date desc",
        )
    except Exception as exc:
        logger.warning("[HR] employee request detail query failed: %s", exc)
        return {
            "request": None,
            "validation_chain": [],
            "note": f"Could not read employee request: {exc}",
            "_source": "get_employee_request_detail",
        }

    if not rows:
        label = request_name or str(request_id)
        return {
            "request": None,
            "validation_chain": [],
            "note": f"No HR request found matching **{label}**.",
            "_source": "get_employee_request_detail",
        }

    row = rows[0]
    request = _present_request(row, include_leave=True)
    validation_chain = _fetch_validation_chain(adapter, row.get("request_approvals_ids"))
    if not validation_chain and (request.get("first_approver") or request.get("second_approver")):
        for label, approver in (
            ("First approver", request.get("first_approver")),
            ("Second approver", request.get("second_approver")),
        ):
            if approver:
                validation_chain.append(
                    {
                        "name": label,
                        "status": "assigned",
                        "approver": approver,
                        "date": None,
                        "sequence": None,
                    }
                )

    return {
        "request": request,
        "validation_chain": validation_chain,
        "employee_name": resolved_name or request.get("employee_name"),
        "employee_file_id": normalize_employee_file_id(employee_file_id) if employee_file_id else None,
        "request_id": request.get("id"),
        "_source": "get_employee_request_detail",
    }

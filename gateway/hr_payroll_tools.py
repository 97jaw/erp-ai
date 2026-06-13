"""Payslip tools — File ID = emp_id; multi-strategy Odoo search with diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from admin.auth.config import auth_db_enabled
from admin.auth.odoo_verify import verify_file_id_with_odoo
from admin.auth.principal import CurrentUser
from adapters.v14.connector import OdooV14Adapter
from gateway.hr_identity import (
    build_hr_identity_prompt,
    can_access_employee_file_id,
    can_query_other_employees,
    discover_employee_identifier_fields,
    employee_id_field_names,
    normalize_employee_file_id,
    resolve_employee_by_file_id,
    resolve_target_employee,
)
from gateway.core.hr_payroll_composer import payslip_period_domain_from_dates

logger = logging.getLogger(__name__)

_PAYSLIP_FIELD_CANDIDATES = (
    "name",
    "number",
    "employee_id",
    "date_from",
    "date_to",
    "state",
    "net_wage",
    "gross_wage",
    "amount",
    "total_paid",
    "credit_note",
    "company_id",
)


async def _load_user_row(user: CurrentUser) -> dict[str, Any] | None:
    if not auth_db_enabled():
        return {"file_id": user.file_id, "odoo_user_id": None}
    from admin.auth.service import get_auth_service

    service = await get_auth_service()
    if service is None:
        return None
    row = await service._users.get_by_id(user.id)
    return dict(row) if row else None


async def resolve_odoo_user_id(user: CurrentUser, adapter: OdooV14Adapter) -> int | None:
    row = await _load_user_row(user)
    if row and row.get("odoo_user_id"):
        return int(row["odoo_user_id"])

    file_id = normalize_employee_file_id(user.file_id)
    if not file_id:
        return None

    employee, _ = resolve_employee_by_file_id(adapter, file_id)
    if employee:
        related = employee.get("user_id")
        if isinstance(related, (list, tuple)) and related:
            return int(related[0])

    verified = await verify_file_id_with_odoo(file_id)
    if verified and verified.get("odoo_user_id"):
        odoo_uid = int(verified["odoo_user_id"])
        if auth_db_enabled() and row:
            from admin.auth.service import get_auth_service

            service = await get_auth_service()
            if service is not None:
                await service._users.set_odoo_user_id(user.id, odoo_uid)
        return odoo_uid

    users = adapter.search_read(
        "res.users",
        [["login", "=", file_id], ["active", "=", True]],
        ["id"],
        limit=1,
    )
    return int(users[0]["id"]) if users else None


def _payslip_model(adapter: OdooV14Adapter) -> str | None:
    if adapter._get_model_fields("hr.payslip"):
        return "hr.payslip"
    return None


def _payslip_read_fields(adapter: OdooV14Adapter) -> list[str]:
    available = adapter._get_model_fields("hr.payslip") or {}
    if not available:
        return list(_PAYSLIP_FIELD_CANDIDATES)
    return [f for f in _PAYSLIP_FIELD_CANDIDATES if f in available]


def _normalize_domain_fragment(part: list[Any]) -> list[Any]:
    """Normalize a domain fragment for safe merging."""
    if not part:
        return []
    if isinstance(part[0], str) and part[0] in ("&", "|", "!"):
        return list(part)
    if (
        len(part) == 3
        and isinstance(part[0], str)
        and part[0] not in ("&", "|", "!")
    ):
        return [list(part)]
    if (
        len(part) == 1
        and isinstance(part[0], (list, tuple))
        and len(part[0]) == 3
        and isinstance(part[0][0], str)
        and part[0][0] not in ("&", "|", "!")
    ):
        return [list(part[0])]
    if all(
        isinstance(item, (list, tuple))
        and len(item) == 3
        and isinstance(item[0], str)
        and item[0] not in ("&", "|", "!")
        for item in part
    ):
        return [list(item) for item in part]
    return list(part)


def _and_domain(*parts: list[Any]) -> list[Any]:
    """Prefix-AND Odoo domains (each part is one leaf triple or nested domain)."""
    domains: list[list[Any]] = []
    for part in parts:
        normalized = _normalize_domain_fragment(part)
        if normalized:
            domains.append(normalized)
    if not domains:
        return []
    if len(domains) == 1:
        return domains[0]
    merged = domains[0]
    for extra in domains[1:]:
        merged = ["&"] + merged + extra
    return merged


def _safe_payslip_order(adapter: OdooV14Adapter) -> str:
    meta = adapter._get_model_fields("hr.payslip") or {}
    for field in ("date_to", "date_from", "create_date", "write_date", "id"):
        if field in meta or field == "id":
            return f"{field} desc"
    return "id desc"


def _payslip_state_domains(adapter: OdooV14Adapter, base: list[Any]) -> list[tuple[str, list[Any]]]:
    """Try progressively looser state filters."""
    payslip_meta = adapter._get_model_fields("hr.payslip") or {}
    if "state" not in payslip_meta:
        return [("no_state_field", base)]

    variants: list[tuple[str, list[Any]]] = [
        ("exclude_cancel", _and_domain(base, ["state", "!=", "cancel"])),
        (
            "done_verify_draft",
            _and_domain(
                base,
                ["state", "in", ["done", "paid", "verify", "close", "draft", "confirmed"]],
            ),
        ),
        ("any_state", base),
    ]
    return variants


def _payslip_search_plans(
    adapter: OdooV14Adapter,
    file_id: str,
    *,
    employee_id: int | None = None,
) -> list[tuple[str, list[Any]]]:
    """Build candidate hr.payslip domains (employee_id + related emp_id paths)."""
    normalized = normalize_employee_file_id(file_id)
    employee_fields = discover_employee_identifier_fields(adapter)
    plans: list[tuple[str, list[Any]]] = []

    if employee_id:
        plans.append(("employee_id", [["employee_id", "=", employee_id]]))

    if not normalized:
        return plans

    available_emp = adapter._get_model_fields("hr.employee") or {}
    for field in employee_fields:
        if field not in available_emp:
            continue
        rel = f"employee_id.{field}"
        plans.append((rel, [[rel, "=", normalized]]))
        plans.append((f"{rel}_ilike", [[rel, "ilike", normalized]]))
        if normalized.isdigit():
            plans.append((f"{rel}_int", [[rel, "=", int(normalized)]]))
            # Some DBs store emp_id as string "2721" on integer-like custom fields
            plans.append((f"{rel}_str", [[rel, "=", str(int(normalized))]]))

    return plans


def _present_payslip(row: dict[str, Any]) -> dict[str, Any]:
    employee = row.get("employee_id")
    employee_name = (
        employee[1] if isinstance(employee, (list, tuple)) and len(employee) > 1 else employee
    )
    amount = (
        row.get("net_wage")
        or row.get("amount")
        or row.get("total_paid")
        or row.get("gross_wage")
    )
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "number": row.get("number"),
        "employee_name": employee_name,
        "date_from": row.get("date_from"),
        "date_to": row.get("date_to"),
        "state": row.get("state"),
        "net_wage": row.get("net_wage"),
        "gross_wage": row.get("gross_wage"),
        "amount": amount,
    }


def fetch_recent_payslips(
    adapter: OdooV14Adapter,
    *,
    limit: int = 10,
    employee_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Recent payslips without File ID — for HR/admin when scoped lookup returns nothing."""
    limit = min(max(int(limit or 5), 1), 50)
    model = _payslip_model(adapter)
    if not model:
        return {
            "payslips": [],
            "count": 0,
            "note": "Model hr.payslip is not installed or not visible to the API user.",
            "scope": "recent",
        }

    fields = _payslip_read_fields(adapter)
    order = _safe_payslip_order(adapter)
    base: list[Any] = []
    if employee_ids:
        base = [["employee_id", "in", employee_ids]]

    for _state_name, domain in _payslip_state_domains(adapter, base):
        try:
            rows = adapter.search_read(
                model=model,
                domain=domain,
                fields=fields,
                limit=limit,
                order=order,
            )
        except Exception as exc:
            logger.warning("[HR] recent payslips failed: %s", exc)
            continue
        if rows:
            payslips = [_present_payslip(row) for row in rows]
            return {
                "payslips": payslips,
                "count": len(payslips),
                "scope": "recent",
                "payslip_match": "recent_unscoped",
                "latest_amount": payslips[0].get("amount"),
            }

    return {
        "payslips": [],
        "count": 0,
        "scope": "recent",
        "note": "No payslips visible to the Odoo API user (check payroll record rules).",
    }


def fetch_payslips_by_file_id(
    adapter: OdooV14Adapter,
    file_id: str,
    *,
    limit: int = 10,
    employee: dict[str, Any] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Search payslips using every safe strategy until records are found.
    Returns diagnostics in `searches_tried` for troubleshooting.
    """
    limit = min(max(int(limit or 5), 1), 50)
    normalized = normalize_employee_file_id(file_id)
    model = _payslip_model(adapter)
    searches_tried: list[str] = []

    if not model:
        return {
            "payslips": [],
            "count": 0,
            "file_id": normalized,
            "note": "Model hr.payslip is not installed or not visible to the API user.",
            "searches_tried": searches_tried,
        }

    employee_id = int(employee["id"]) if employee else None
    if employee is None and normalized:
        employee, match = resolve_employee_by_file_id(adapter, normalized)
        searches_tried.append(f"employee_lookup:{match or 'not_found'}")
        if employee:
            employee_id = int(employee["id"])

    fields = _payslip_read_fields(adapter)
    order = _safe_payslip_order(adapter)
    plans = _payslip_search_plans(adapter, normalized or file_id, employee_id=employee_id)

    for plan_name, base_domain in plans:
        period_domain = list(base_domain)
        if date_from and date_to:
            period_domain = _and_domain(period_domain, payslip_period_domain_from_dates(date_from, date_to))
        elif date_from:
            period_domain.append(["date_from", ">=", date_from])
        elif date_to:
            period_domain.append(["date_to", "<=", date_to])
        search_limit = 1 if date_from and date_to else limit
        for state_name, domain in _payslip_state_domains(adapter, period_domain):
            label = f"{plan_name}/{state_name}"
            searches_tried.append(label)
            try:
                rows = adapter.search_read(
                    model=model,
                    domain=domain,
                    fields=fields,
                    limit=search_limit,
                    order=order,
                )
            except Exception as exc:
                searches_tried.append(f"{label}:error={exc}")
                logger.warning("[HR] payslip %s failed: %s", label, exc)
                continue
            if rows:
                payslips = [_present_payslip(row) for row in rows]
                return {
                    "payslips": payslips,
                    "count": len(payslips),
                    "file_id": normalized,
                    "employee_id": employee_id,
                    "employee_name": (employee or {}).get("name"),
                    "employee_match": searches_tried[0] if searches_tried else None,
                    "payslip_match": label,
                    "latest_amount": payslips[0].get("amount"),
                    "searches_tried": searches_tried,
                }

    # Last resort: any payslips for resolved employee without date ordering issues
    if employee_id:
        searches_tried.append("employee_id_fallback_any")
        try:
            rows = adapter.search_read(
                model=model,
                domain=[["employee_id", "=", employee_id]],
                fields=fields,
                limit=limit,
                order="id desc",
            )
            if rows:
                payslips = [_present_payslip(row) for row in rows]
                return {
                    "payslips": payslips,
                    "count": len(payslips),
                    "file_id": normalized,
                    "employee_id": employee_id,
                    "employee_name": employee.get("name") if employee else None,
                    "payslip_match": "employee_id_fallback_any",
                    "latest_amount": payslips[0].get("amount"),
                    "searches_tried": searches_tried,
                }
        except Exception as exc:
            searches_tried.append(f"employee_id_fallback_any:error={exc}")

    note_parts = []
    if not employee and normalized:
        note_parts.append(
            f"No hr.employee found for File ID '{normalized}' "
            f"(tried fields: {', '.join(employee_id_field_names())})."
        )
    elif employee_id:
        note_parts.append(
            f"Employee '{(employee or {}).get('name')}' (id {employee_id}) has no payslips "
            "matching any search strategy."
        )
    else:
        note_parts.append("Could not resolve employee or File ID for payslip search.")

    return {
        "payslips": [],
        "count": 0,
        "file_id": normalized,
        "employee_id": employee_id,
        "employee_name": (employee or {}).get("name"),
        "note": " ".join(note_parts),
        "searches_tried": searches_tried,
    }


async def get_my_payslips(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    file_id = normalize_employee_file_id(user.file_id)
    if not can_access_employee_file_id(user, file_id):
        return {
            "payslips": [],
            "count": 0,
            "note": "Not allowed to view these payslips.",
        }

    odoo_uid = await resolve_odoo_user_id(user, adapter)
    employee = None
    if file_id or odoo_uid:
        employee, _ = resolve_employee_by_file_id(
            adapter,
            file_id or user.file_id or "",
            odoo_user_id=odoo_uid,
        )

    payload = fetch_payslips_by_file_id(
        adapter,
        file_id or user.file_id or "",
        limit=limit,
        employee=employee,
    )
    payload["scope"] = "self"

    if payload.get("count", 0) == 0 and can_query_other_employees(user):
        recent = fetch_recent_payslips(adapter, limit=limit)
        if recent.get("count", 0) > 0:
            payload = {
                **recent,
                "scope": "self_with_recent_fallback",
                "file_id": file_id,
                "note": (
                    (payload.get("note") or "")
                    + " Showing recent payslips from Odoo because your File ID did not match "
                    "a payslip directly."
                ).strip(),
                "searches_tried": payload.get("searches_tried", []),
            }

    return payload


async def get_employee_payslips(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str,
    limit: int = 5,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    target = normalize_employee_file_id(employee_file_id)
    if not can_access_employee_file_id(user, target):
        return {
            "payslips": [],
            "count": 0,
            "note": "You may only view your own HR records without admin Odoo access.",
        }

    payload = fetch_payslips_by_file_id(
        adapter,
        target,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
    )
    payload["scope"] = "other" if target != normalize_employee_file_id(user.file_id) else "self"
    payload["_source"] = "get_employee_payslips"
    return payload


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


def _resolve_payslip_for_employee(
    adapter: OdooV14Adapter,
    *,
    employee_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any] | None:
    if not employee_id:
        return None
    model = _payslip_model(adapter)
    if not model:
        return None
    domain: list[Any] = [["employee_id", "=", employee_id]]
    if date_from and date_to:
        domain = _and_domain(domain, payslip_period_domain_from_dates(date_from, date_to))
    elif date_from:
        domain.append(["date_from", ">=", date_from])
    elif date_to:
        domain.append(["date_to", "<=", date_to])
    fields = _payslip_read_fields(adapter) + [
        "fine",
        "advance",
        "total_deductions",
        "net_salary",
        "labor_snapshot_total_salary",
        "staff_snapshot_total_salary",
        "weekend_ot_hours",
        "normal_ot_hours",
        "holiday_ot_hours",
        "total_over_time",
        "sick_leave_full_paid_amount",
        "sick_leave_half_paid_amount",
        "sick_leave_unpaid_amount",
    ]
    available = adapter._get_model_fields("hr.payslip") or {}
    fields = [field for field in fields if field in available or field in ("id", "name", "employee_id")]
    try:
        rows = adapter.search_read(
            model=model,
            domain=domain,
            fields=fields,
            limit=1,
            order=_safe_payslip_order(adapter),
        )
    except Exception as exc:
        logger.warning("[HR] payslip resolve failed: %s", exc)
        return None
    return rows[0] if rows else None


async def get_payslip_detail(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str | None = None,
    employee_name: str | None = None,
    detail_type: str = "lines",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return payslip salary lines or project cost allocation for one employee."""
    employee: dict[str, Any] | None = None
    employee_id: int | None = None
    resolved_file_id = normalize_employee_file_id(employee_file_id) if employee_file_id else None

    if resolved_file_id:
        if not can_access_employee_file_id(user, resolved_file_id):
            return {
                "detail_type": detail_type,
                "lines": [],
                "allocations": [],
                "count": 0,
                "note": "You may only view your own HR records without admin Odoo access.",
                "_source": "get_payslip_detail",
            }
        employee, _ = resolve_employee_by_file_id(adapter, resolved_file_id)
        if employee:
            employee_id = int(employee["id"])

    if employee_id is None and employee_name:
        matches = _search_employees_by_name(adapter, employee_name, limit=5)
        if len(matches) == 1:
            employee = matches[0]
            employee_id = int(employee["id"])
        elif len(matches) > 1:
            return {
                "detail_type": detail_type,
                "lines": [],
                "allocations": [],
                "count": 0,
                "employee_name": employee_name,
                "ambiguous_employees": [
                    {
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "emp_id": row.get("emp_id"),
                    }
                    for row in matches
                ],
                "note": f"Multiple employees match '{employee_name}'. Please specify file ID or full name.",
                "_source": "get_payslip_detail",
            }

    payslip = _resolve_payslip_for_employee(
        adapter,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
    )
    if not payslip:
        label = (employee or {}).get("name") or employee_name or resolved_file_id or "that employee"
        return {
            "detail_type": detail_type,
            "lines": [],
            "allocations": [],
            "count": 0,
            "employee_name": (employee or {}).get("name") or employee_name,
            "employee_file_id": resolved_file_id,
            "note": f"No payslip found for **{label}** for the requested period.",
            "_source": "get_payslip_detail",
        }

    payslip_id = int(payslip["id"])
    employee_label = (employee or {}).get("name") or employee_name
    header = _present_payslip(payslip)
    deductions_summary = {
        "fine": payslip.get("fine"),
        "advance": payslip.get("advance"),
        "total_deductions": payslip.get("total_deductions"),
        "net_salary": payslip.get("net_salary") or payslip.get("net_wage"),
        "gross_wage": payslip.get("gross_wage"),
        "labor_snapshot_total_salary": payslip.get("labor_snapshot_total_salary"),
        "staff_snapshot_total_salary": payslip.get("staff_snapshot_total_salary"),
    }

    if detail_type == "header":
        return {
            "detail_type": detail_type,
            "payslip": header,
            "count": 1,
            "employee_name": employee_label,
            "employee_file_id": resolved_file_id,
            "deductions_summary": deductions_summary,
            "_source": "get_payslip_detail",
        }

    if detail_type == "distribution":
        month = None
        year = None
        date_to_val = str(payslip.get("date_to") or "")
        if len(date_to_val) >= 7:
            year = date_to_val[:4]
            month = str(int(date_to_val[5:7]))
        alloc_domain: list[Any] = [["employee_id", "=", employee_id or payslip.get("employee_id")[0]]]
        if month and year:
            alloc_domain.extend([["month", "=", month], ["year", "=", year]])
        try:
            rows = adapter.search_read(
                model="hr.payslip.cost.allocation",
                domain=alloc_domain,
                fields=["project_id", "allocation", "amount", "total_salary", "month", "year"],
                limit=limit,
                order="amount desc",
            )
        except Exception as exc:
            return {
                "detail_type": detail_type,
                "payslip": header,
                "allocations": [],
                "count": 0,
                "employee_name": employee_label,
                "note": f"Could not load payslip distribution: {exc}",
                "_source": "get_payslip_detail",
            }
        allocations = []
        for row in rows:
            project = row.get("project_id")
            project_name = (
                project[1] if isinstance(project, (list, tuple)) and len(project) > 1 else project
            )
            allocations.append(
                {
                    "project_name": project_name,
                    "allocation": row.get("allocation"),
                    "amount": row.get("amount"),
                    "total_salary": row.get("total_salary"),
                }
            )
        return {
            "detail_type": detail_type,
            "payslip": header,
            "allocations": allocations,
            "count": len(allocations),
            "employee_name": employee_label,
            "employee_file_id": resolved_file_id,
            "_source": "get_payslip_detail",
        }

    line_fields = ["name", "code", "amount", "quantity", "rate", "category_id"]
    available_lines = adapter._get_model_fields("hr.payslip.line") or {}
    line_fields = [field for field in line_fields if field in available_lines or field in ("name", "code", "amount")]
    try:
        lines = adapter.search_read(
            model="hr.payslip.line",
            domain=[["slip_id", "=", payslip_id]],
            fields=line_fields,
            limit=limit,
            order="sequence asc, id asc",
        )
    except Exception as exc:
        return {
            "detail_type": detail_type,
            "payslip": header,
            "lines": [],
            "count": 0,
            "employee_name": employee_label,
            "note": f"Could not load payslip lines: {exc}",
            "_source": "get_payslip_detail",
        }

    return {
        "detail_type": detail_type,
        "payslip": header,
        "lines": lines,
        "count": len(lines),
        "employee_name": employee_label,
        "employee_file_id": resolved_file_id,
        "deductions_summary": deductions_summary,
        "_source": "get_payslip_detail",
    }


async def list_recent_payslips(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    limit: int = 10,
) -> dict[str, Any]:
    if not can_query_other_employees(user):
        return {
            "payslips": [],
            "count": 0,
            "note": "Listing all payslips requires HR admin or full Odoo access.",
        }
    return fetch_recent_payslips(adapter, limit=limit)


__all__ = [
    "build_hr_identity_prompt",
    "fetch_payslips_by_file_id",
    "fetch_recent_payslips",
    "get_employee_payslips",
    "get_my_payslips",
    "get_payslip_detail",
    "list_recent_payslips",
    "resolve_odoo_user_id",
]

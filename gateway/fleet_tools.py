"""Fleet vehicle reads — driver, employee link, project, and location."""

from __future__ import annotations

import logging
import re
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

_FLEET_MODEL = "fleet.vehicle"
_FLEET_FIELD_CANDIDATES = (
    "name",
    "license_plate",
    "model_id",
    "driver_id",
    "employee_id",
    "emp_id",
    "emp_mobile",
    "project_id",
    "location",
    "state_id",
    "vin_sn",
    "vehicle_type",
    "company_id",
    "active",
)
_PLATE_RE = re.compile(
    r"\b(?:plate|license\s*plate|registration)\s*[:\s#-]*([A-Za-z0-9-]{3,12})\b",
    re.I,
)


def _fleet_fields(adapter: OdooV14Adapter) -> list[str]:
    available = adapter._get_model_fields(_FLEET_MODEL) or {}
    if not available:
        return list(_FLEET_FIELD_CANDIDATES)
    return [field for field in _FLEET_FIELD_CANDIDATES if field in available]


def extract_license_plate(message: str) -> str | None:
    """Extract a license plate token from natural language."""
    match = _PLATE_RE.search(message or "")
    if match:
        return match.group(1).strip().upper()
    return None


def _many2one_label(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _many2one_id(value: Any) -> int | None:
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    return None


def _present_vehicle(row: dict[str, Any]) -> dict[str, Any]:
    driver = row.get("driver_id")
    employee = row.get("employee_id")
    project = row.get("project_id")
    model = row.get("model_id")
    state = row.get("state_id")
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "license_plate": row.get("license_plate"),
        "model": _many2one_label(model),
        "driver_name": _many2one_label(driver),
        "driver_id": _many2one_id(driver),
        "employee_name": _many2one_label(employee),
        "employee_id": _many2one_id(employee),
        "file_id": row.get("emp_id"),
        "mobile": row.get("emp_mobile"),
        "project_name": _many2one_label(project),
        "project_id": _many2one_id(project),
        "location": row.get("location"),
        "state": _many2one_label(state),
        "vin": row.get("vin_sn"),
        "vehicle_type": row.get("vehicle_type"),
    }


def _search_employees_by_name(
    adapter: OdooV14Adapter,
    name_hint: str,
    *,
    limit: int = 5,
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
        logger.warning("[Fleet] employee name search failed: %s", exc)
        return []


async def search_fleet_vehicles(
    adapter: OdooV14Adapter,
    user: CurrentUser,
    *,
    employee_file_id: str | None = None,
    employee_name: str | None = None,
    license_plate: str | None = None,
    project_name: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search fleet.vehicle with employee, plate, or project filters."""
    limit = min(max(int(limit or 20), 1), 50)
    if not adapter._get_model_fields(_FLEET_MODEL):
        return {
            "vehicles": [],
            "count": 0,
            "note": "Fleet module is not available on this Odoo instance.",
            "_source": "search_fleet_vehicles",
        }

    domain: list[Any] = [["active", "=", True]]
    resolved_name = employee_name
    employee_id: int | None = None

    if employee_file_id:
        target = normalize_employee_file_id(employee_file_id)
        if not can_access_employee_file_id(user, target):
            return {
                "vehicles": [],
                "count": 0,
                "note": "You may only view your own HR records without admin Odoo access.",
                "_source": "search_fleet_vehicles",
            }
        employee, _ = resolve_employee_by_file_id(adapter, target)
        if employee:
            employee_id = int(employee["id"])
            resolved_name = str(employee.get("name") or resolved_name or "")
        else:
            return {
                "vehicles": [],
                "count": 0,
                "employee_file_id": target,
                "note": f"No employee found for file ID {target}.",
                "_source": "search_fleet_vehicles",
            }

    if employee_id is None and employee_name:
        matches = _search_employees_by_name(adapter, employee_name, limit=5)
        if len(matches) == 1:
            employee_id = int(matches[0]["id"])
            resolved_name = str(matches[0].get("name") or employee_name)
        elif len(matches) > 1:
            return {
                "vehicles": [],
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
                "_source": "search_fleet_vehicles",
            }

    available = adapter._get_model_fields(_FLEET_MODEL) or {}
    if employee_id is not None:
        clauses: list[list[Any]] = []
        if "employee_id" in available:
            clauses.append(["employee_id", "=", employee_id])
        if "driver_id" in available:
            clauses.append(["driver_id", "=", employee_id])
        if "emp_id" in available and employee_file_id:
            clauses.append(["emp_id", "=", normalize_employee_file_id(employee_file_id)])
        if clauses:
            if len(clauses) == 1:
                domain.extend(clauses)
            else:
                domain.extend(["|"] * (len(clauses) - 1))
                domain.extend(clauses)
        elif employee_name:
            if "driver_id.name" in available or "employee_id.name" in available:
                domain.extend(build_employee_name_domain(employee_name))
    elif employee_name:
        name_clauses: list[list[Any]] = []
        if "driver_id.name" in available:
            name_clauses.append(["driver_id.name", "ilike", employee_name.split()[0]])
        if "employee_id.name" in available:
            name_clauses.append(["employee_id.name", "ilike", employee_name.split()[0]])
        if name_clauses:
            if len(name_clauses) == 1:
                domain.extend(name_clauses)
            else:
                domain.append("|")
                domain.extend(name_clauses)

    if license_plate:
        domain.append(["license_plate", "ilike", license_plate.strip()])
    if project_name and "project_id.name" in available:
        domain.append(["project_id.name", "ilike", project_name.strip()])

    try:
        rows = adapter.search_read(
            model=_FLEET_MODEL,
            domain=domain,
            fields=_fleet_fields(adapter),
            limit=limit,
            order="name asc",
        )
    except Exception as exc:
        logger.warning("[Fleet] fleet.vehicle query failed: %s", exc)
        return {
            "vehicles": [],
            "count": 0,
            "note": f"Could not read fleet vehicles: {exc}",
            "_source": "search_fleet_vehicles",
        }

    vehicles = [_present_vehicle(row) for row in rows]
    return {
        "vehicles": vehicles,
        "count": len(vehicles),
        "employee_name": resolved_name,
        "employee_file_id": normalize_employee_file_id(employee_file_id) if employee_file_id else None,
        "license_plate": license_plate,
        "project_name": project_name,
        "note": (
            f"No fleet vehicles found for **{resolved_name}**."
            if resolved_name and not vehicles
            else (
                "No fleet vehicles found matching that criteria."
                if not vehicles
                else None
            )
        ),
        "_source": "search_fleet_vehicles",
    }

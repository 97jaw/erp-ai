"""Deterministic HR query routing for open-gate universal tools (Phase M2.2b).

Maps natural-language HR questions to query_odoo / aggregate_odoo payloads
without new Odoo tools.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

_HR_SUBJECT_TOKENS = ("employee", "staff", "manager", "payroll", "hr", "labor", "labour", "foreman", "forman")
_REQUEST_TOKENS = (
    "leave request",
    "leave requests",
    "pending leave",
    "resignation",
    "resignations",
    "termination",
    "terminations",
    "terminated",
    "promotion request",
    "promotion requests",
    "loan request",
    "loan requests",
    "transfer",
    "transfers",
    "unresolved request",
    "unresolved requests",
    "pending request",
    "employee request",
    "employee requests",
)
_ATTENDANCE_TOKENS = (
    "attendance",
    "absent",
    "absence",
    "on leave today",
    "work hours",
    "work hour",
    "present today",
)
_COMPLIANCE_TOKENS = (
    "visa",
    "visas",
    "labour card",
    "labor card",
    "passport",
    "passports",
    "eid",
    "emirates id",
    "missing document",
    "missing documents",
    "missing required",
)
_STOCK_TRANSFER_GUARD = ("stock", "inventory", "warehouse", "move line", "quant")
_PROJECT_TASK_GUARD = ("project task", "task record", "milestone")
_SEPARATION_GUARD_TOKENS = (
    "terminated",
    "termination",
    "terminations",
    "fired",
    "clearance",
    "separation",
    "resignation",
    "resignations",
)


def _query_blob(message: str, intent: Intent) -> str:
    return f"{message} {intent.specific_intent} {intent.subject_area}".lower().replace("_", " ")


def is_hr_orchestration_query(message: str, intent: Intent) -> bool:
    blob = _query_blob(message, intent)
    from gateway.core.payroll_query_routing import is_payroll_orchestration_query

    if is_payroll_orchestration_query(message, intent):
        return False
    if intent.subject_area == "hr":
        return True
    if any(token in blob for token in _HR_SUBJECT_TOKENS):
        return True
    if any(token in blob for token in _REQUEST_TOKENS + _ATTENDANCE_TOKENS + _COMPLIANCE_TOKENS):
        return True
    if "branch" in blob or "branches" in blob:
        return True
    if "department head" in blob or "head of" in blob:
        return True
    if "who works on" in blob or "works on" in blob:
        return True
    if re.search(r"who works(?:\s+in|\s+at)?", blob):
        return True
    if "head count by project" in blob or "headcount by project" in blob:
        return True
    return False


def is_hr_person_query(message: str) -> bool:
    blob = message.lower()
    if any(token in blob for token in ("vehicle", "fleet", "car ", "assigned vehicle")):
        return True
    if "project history" in blob:
        return True
    if re.search(r"show me .+ details", blob):
        return True
    if re.search(r".+'s assigned", blob):
        return True
    if re.search(r".+ attendance this month", blob):
        return True
    return False


def is_hr_cross_module_query(message: str) -> bool:
    blob = message.lower()
    return any(
        token in blob
        for token in (
            "assigned vehicle",
            "project history",
            "head count by project",
            "headcount by project",
            "department head count by project",
        )
    )


def is_hr_project_staff_query(message: str) -> bool:
    blob = message.lower()
    return "who works on" in blob or "employees on project" in blob or "staff on project" in blob


def _confirmed_project_id(context: ContextStack | None) -> int | None:
    if context is None:
        return None
    facts = context.working_memory.session_facts or {}
    confirmed = facts.get("confirmed_entities") or {}
    project = confirmed.get("project") or {}
    pid = project.get("id")
    if pid:
        return int(pid)
    resolved = facts.get("resolved_project_id") or facts.get("last_expense_summary_project_id")
    return int(resolved) if resolved else None


def _month_attendance_key(temporal: Any) -> str:
    today = temporal.today
    return f"{today.year:04d}-{today.month:02d}"


def _date_window(message: str, intent: Intent, context: ContextStack | None) -> tuple[str, str]:
    from gateway.core.strategy_planner import resolve_report_date_range

    temporal = context.temporal_context if context else None
    if temporal is None:
        from gateway.core.temporal_context import TemporalContext

        temporal = TemporalContext.build()
    return resolve_report_date_range(_query_blob(message, intent), temporal)


def resolve_hr_tool(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_name, payload) for HR queries, or None if not HR-routed."""
    if not is_hr_orchestration_query(message, intent):
        return None

    blob = _query_blob(message, intent)
    temporal = context.temporal_context if context else None
    if temporal is None:
        from gateway.core.temporal_context import TemporalContext

        temporal = TemporalContext.build()

    date_from, date_to = _date_window(message, intent, context)
    active_domain: list[Any] = [["active", "=", True]]

    # --- Cross-module: who works on project ---
    project_id = _confirmed_project_id(context)
    if is_hr_project_staff_query(message) and project_id is not None:
        return "query_odoo", {
            "model": "hr.employee",
            "domain": active_domain + [["project_id", "=", project_id]],
            "fields": ["name", "emp_id", "job_id", "department_id", "project_id"],
            "limit": 50,
        }

    if "head count by project" in blob or "headcount by project" in blob or (
        "department" in blob and "by project" in blob
    ):
        return "aggregate_odoo", {
            "model": "hr.employee",
            "domain": active_domain,
            "group_by": ["project_id", "department_id"],
            "aggregates": ["id:count"],
            "limit": 200,
        }

    # --- Labor vs staff ---
    if any(token in blob for token in ("labor vs staff", "labour vs staff", "labor and staff")) or (
        ("labor" in blob or "labour" in blob or "worker" in blob)
        and ("staff" in blob or " vs " in blob)
        and ("how many" in blob or "count" in blob)
    ):
        return "aggregate_odoo", {
            "model": "hr.employee",
            "domain": active_domain,
            "group_by": ["is_labor"],
            "aggregates": ["id:count"],
            "limit": 10,
        }

    # --- Separation / termination counts (before generic headcount) ---
    from gateway.core.hr_payroll_composer import (
        compose_hr_request_detail_plan,
        compose_hr_request_plan,
        compose_separation_plan,
        plan_to_route,
    )

    separation_plan = compose_separation_plan(message, intent, context)
    if separation_plan is not None:
        routed = plan_to_route(separation_plan)
        if routed is not None:
            return routed

    hr_request_detail_plan = compose_hr_request_detail_plan(message, intent, context)
    if hr_request_detail_plan is not None:
        routed = plan_to_route(hr_request_detail_plan)
        if routed is not None:
            return routed

    hr_request_plan = compose_hr_request_plan(message, intent, context)
    if hr_request_plan is not None:
        routed = plan_to_route(hr_request_plan)
        if routed is not None:
            return routed

    # --- HR requests (employee.requests) — legacy keyword fallback ---
    is_hr_request = any(token in blob for token in _REQUEST_TOKENS) or (
        "request" in blob
        and ("employee" in blob or intent.subject_area == "hr")
        and not any(g in blob for g in _PROJECT_TASK_GUARD)
    )
    if is_hr_request and not (
        any(g in blob for g in _STOCK_TRANSFER_GUARD) and "employee" not in blob
    ):
        domain: list[Any] = []
        if "pending" in blob or "unresolved" in blob:
            domain.append(["is_approve", "=", False])
        elif "approved" in blob or "approve" in blob:
            domain.append(["is_approve", "=", True])
        if "leave" in blob:
            domain.append(["request_type_id.name", "ilike", "leave"])
        elif "resign" in blob:
            domain.append(["request_type_id.name", "ilike", "resign"])
        elif "termin" in blob or "fired" in blob:
            domain.append(["request_type_id.name", "ilike", "termination"])
        elif "clearance" in blob:
            domain.append(["request_type_id.name", "ilike", "clearance"])
        elif "promotion" in blob:
            domain.append(["request_type_id.name", "ilike", "promotion"])
        elif "loan" in blob:
            domain.append(["request_type_id.name", "ilike", "loan"])
        elif "transfer" in blob:
            domain.append(["request_type_id.name", "ilike", "transfer"])
        if "this month" in blob:
            domain.append(["create_date", ">=", date_from])
            domain.append(["create_date", "<=", date_to])
        elif "this year" in blob and "join" not in blob:
            domain.append(["create_date", ">=", date_from])
            domain.append(["create_date", "<=", date_to])
        elif "last quarter" in blob:
            domain.append(["create_date", ">=", date_from])
            domain.append(["create_date", "<=", date_to])
        return "query_odoo", {
            "model": "employee.requests",
            "domain": domain,
            "fields": [
                "name",
                "employee_id",
                "request_type_id",
                "status",
                "is_approve",
                "create_date",
            ],
            "limit": 50,
            "order": "create_date desc",
        }

    # --- Attendance ---
    if any(token in blob for token in _ATTENDANCE_TOKENS):
        domain = []
        if "today" in blob and "leave" not in blob and "absent" not in blob:
            domain.append(["check_in", ">=", f"{temporal.today.isoformat()} 00:00:00"])
            domain.append(["check_in", "<=", f"{temporal.today.isoformat()} 23:59:59"])
            if "count" in blob or "attendance count" in blob:
                return "aggregate_odoo", {
                    "model": "hr.attendance",
                    "domain": domain,
                    "group_by": ["x_attendance_type"],
                    "aggregates": ["id:count"],
                    "limit": 20,
                }
        if "yesterday" in blob and ("absent" in blob or "absence" in blob):
            yesterday = temporal.today - timedelta(days=1)
            domain.append(["check_in", ">=", f"{yesterday.isoformat()} 00:00:00"])
            domain.append(["check_in", "<=", f"{yesterday.isoformat()} 23:59:59"])
            domain.append(["x_attendance_type", "=", "absent"])
            return "query_odoo", {
                "model": "hr.attendance",
                "domain": domain,
                "fields": ["employee_id", "check_in", "x_attendance_type", "x_is_absent"],
                "limit": 50,
            }
        if "on leave today" in blob or ("leave" in blob and "today" in blob):
            domain.append(["x_attendance_month", "=", _month_attendance_key(temporal)])
            domain.append(["x_attendance_type", "in", ["annual", "sick"]])
            return "query_odoo", {
                "model": "hr.attendance",
                "domain": domain,
                "fields": ["employee_id", "x_attendance_type", "check_in"],
                "limit": 50,
            }
        if "work hours" in blob and "department" in blob:
            domain.append(["x_attendance_month", "=", _month_attendance_key(temporal)])
            domain.append(["x_attendance_type", "=", "present"])
            return "query_odoo", {
                "model": "hr.attendance",
                "domain": domain,
                "fields": ["employee_id", "worked_hours", "x_attendance_type", "check_in"],
                "limit": 100,
            }
        if re.search(r".+ attendance this month", blob):
            name_hint = re.sub(r"\s+attendance this month.*", "", message, flags=re.I).strip(" '\"")
            att_domain: list[Any] = [
                ["x_attendance_month", "=", _month_attendance_key(temporal)],
            ]
            if name_hint:
                parts = [p for p in name_hint.split() if len(p) > 1]
                if parts:
                    att_domain.append(["employee_id.name", "ilike", parts[0]])
                    if len(parts) > 1:
                        att_domain.append(["employee_id.name", "ilike", parts[-1]])
            return "query_odoo", {
                "model": "hr.attendance",
                "domain": att_domain,
                "fields": ["employee_id", "x_attendance_type", "worked_hours", "check_in"],
                "limit": 50,
            }

    # --- Compliance ---
    if any(token in blob for token in _COMPLIANCE_TOKENS):
        domain = list(active_domain)
        if "visa" in blob and ("expir" in blob or "30" in blob):
            end = temporal.today + timedelta(days=30)
            domain.append(["visa_expire", ">=", temporal.today.isoformat()])
            domain.append(["visa_expire", "<=", end.isoformat()])
        elif "labour card" in blob or "labor card" in blob:
            domain.append(["labour_card_expiry_date", "<", temporal.today.isoformat()])
        elif "passport" in blob and "expir" in blob:
            domain.append(["passport_expiry_date", ">=", date_from])
            domain.append(["passport_expiry_date", "<=", date_to])
        elif "missing document" in blob or "missing required" in blob:
            domain.append(["has_missing_required_docs", "=", True])
        elif "eid" in blob or "emirates id" in blob or "identification" in blob:
            end = temporal.today + timedelta(days=90)
            domain.append(["visa_expire", ">=", temporal.today.isoformat()])
            domain.append(["visa_expire", "<=", end.isoformat()])
        return "query_odoo", {
            "model": "hr.employee",
            "domain": domain,
            "fields": [
                "name",
                "emp_id",
                "visa_expire",
                "labour_card_expiry_date",
                "passport_expiry_date",
                "identification_id",
                "has_missing_required_docs",
                "missing_required_doc_names",
            ],
            "limit": 50,
        }

    # --- Foremen ---
    if any(token in blob for token in ("foreman", "forman", "foremen", "coach_id")):
        return "query_odoo", {
            "model": "hr.employee",
            "domain": active_domain
            + ["|", ["job_title", "ilike", "foreman"], ["job_title", "ilike", "forman"]],
            "fields": ["name", "emp_id", "job_title", "coach_id", "department_id"],
            "limit": 50,
        }

    # --- Department head ---
    if "department head" in blob or "head of" in blob:
        dept = "civil" if "civil" in blob else ""
        domain: list[Any] = []
        if dept:
            domain.append(["name", "ilike", dept])
        return "query_odoo", {
            "model": "hr.department",
            "domain": domain,
            "fields": ["name", "manager_id", "total_employee", "parent_id"],
            "limit": 20,
        }

    # --- Biggest department ---
    if any(token in blob for token in ("biggest department", "largest department", "most employees")):
        return "aggregate_odoo", {
            "model": "hr.employee",
            "domain": active_domain,
            "group_by": ["department_id"],
            "aggregates": ["id:count"],
            "limit": 200,
        }

    # --- Branches ---
    if "branch" in blob or "branches" in blob:
        return "aggregate_odoo", {
            "model": "hr.employee",
            "domain": active_domain,
            "group_by": ["branch_id"],
            "aggregates": ["id:count"],
            "limit": 100,
        }

    # --- List departments ---
    if "list all departments" in blob or blob.strip() in ("departments", "all departments"):
        return "query_odoo", {
            "model": "hr.department",
            "domain": [],
            "fields": ["name", "manager_id", "total_employee"],
            "limit": 100,
        }

    # --- Joined this year ---
    if "joined this year" in blob or "joining this year" in blob:
        return "query_odoo", {
            "model": "hr.employee",
            "domain": active_domain
            + [
                ["joining_date", ">=", date_from],
                ["joining_date", "<=", date_to],
            ],
            "fields": ["name", "emp_id", "joining_date", "department_id"],
            "limit": 50,
            "order": "joining_date desc",
        }

    # --- Employee detail by name ---
    detail_match = re.search(r"show me (.+?) details", message, re.I)
    if detail_match or ("details" in blob and intent.subject_area == "hr"):
        name = (detail_match.group(1) if detail_match else message).strip(" '\"")
        if name and name.lower() not in ("employee", "staff"):
            return "query_odoo", {
                "model": "hr.employee",
                "domain": active_domain + [["name", "ilike", name]],
                "fields": [
                    "name",
                    "emp_id",
                    "department_id",
                    "job_id",
                    "job_title",
                    "project_id",
                    "joining_date",
                    "visa_expire",
                ],
                "limit": 5,
            }

    # --- Employee vehicle (after name in message) — handled by search_fleet_vehicles ---
    if "vehicle" in blob or "fleet" in blob or "assigned car" in blob:
        from gateway.core.fleet_query_routing import resolve_fleet_tool

        fleet_route = resolve_fleet_tool(message, intent, context)
        if fleet_route is not None:
            return fleet_route

    # --- Employee project history ---
    if "project history" in blob:
        name_part = message.split("'s")[0].strip() if "'s" in message else ""
        domain = list(active_domain)
        if name_part:
            domain.append(["name", "ilike", name_part.split()[0]])
        return "query_odoo", {
            "model": "hr.employee",
            "domain": domain,
            "fields": ["name", "project_id", "project_id_store", "department_id", "joining_date"],
            "limit": 10,
        }

    # --- Managers ---
    if "manager" in blob and "department head" not in blob:
        return "query_odoo", {
            "model": "hr.employee",
            "domain": active_domain + [["child_ids", "!=", False]],
            "fields": ["name", "job_title", "department_id", "child_ids"],
            "limit": 50,
        }

    # --- Department roster (who works in X department) ---
    if (
        (
            re.search(r"who works(?:\s+in|\s+at)?", blob)
            or "employees in" in blob
            or "staff in" in blob
        )
        and "department" in blob
        and "by project" not in blob
        and "head count" not in blob
        and "headcount" not in blob
    ):
        roster_domain: list[Any] = list(active_domain)
        dept_match = re.search(
            r"(?:in|at|from)\s+(?:the\s+)?([a-z][a-z\s&.-]+?)\s+department",
            message,
            re.I,
        )
        if "civil" in blob:
            roster_domain.append(["department_id.name", "ilike", "civil"])
        elif dept_match:
            roster_domain.append(["department_id.name", "ilike", dept_match.group(1).strip()])
        return "query_odoo", {
            "model": "hr.employee",
            "domain": roster_domain,
            "fields": ["name", "job_id", "department_id", "work_email"],
            "limit": 100,
            "order": "name asc",
        }

    # --- Default headcount (existing open-gate behavior, refined) ---
    domain = list(active_domain)
    if "civil" in blob and ("department" in blob or "employees in" in blob):
        domain.append(["department_id.name", "ilike", "civil"])

    if "department" in blob or "per department" in blob or "how many" in blob or intent.expected_output == "number":
        if intent.primary_action == "analyze" and "department" in blob:
            return "aggregate_odoo", {
                "model": "hr.employee",
                "domain": domain,
                "group_by": ["department_id"],
                "aggregates": ["id:count"],
                "limit": 200,
            }
        return "aggregate_odoo", {
            "model": "hr.employee",
            "domain": domain,
            "group_by": ["department_id"],
            "aggregates": ["id:count"],
            "limit": 200,
        }

    if "civil" in blob:
        domain.append(["department_id.name", "ilike", "civil"])
    return "query_odoo", {
        "model": "hr.employee",
        "domain": domain,
        "fields": ["name", "job_id", "department_id"],
        "limit": 50,
    }

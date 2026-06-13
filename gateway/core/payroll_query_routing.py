"""Deterministic payroll query routing for open-gate universal tools (Phase M6).

Maps payroll / labor-cost questions to query_odoo / aggregate_odoo payloads
without new Odoo tools.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

WORKED_DAYS_MODEL = "hr.payslip.worked_days"
COST_ALLOCATION_MODEL = "hr.payslip.cost.allocation"

_PAYROLL_SUBJECT_TOKENS = (
    "payroll",
    "payslip",
    "payslips",
    "salary slip",
    "salary slips",
    "net salary",
    "cost allocation",
    "labor cost",
    "labour cost",
    "labor costs",
    "labour costs",
    "payroll cost",
    "payroll costs",
    "overtime",
    "deduction",
    "deductions",
    "payslip run",
    "salary batch",
    "fine",
    "fines",
    "advance",
    "advances",
    "finalized",
    "draft payslip",
    "job mission",
    "annual leave salary",
    "sick leave cost",
    "sick leave usage",
    "worked days",
    "worked_days",
)
_LABOR_COST_RE = re.compile(
    r"\b(labor|labour)\s+costs?\b|\bpayroll\s+costs?\b|\bcost\s+allocation\b",
    re.I,
)
_EMPLOYEE_NAME_RE = re.compile(
    r"(?:payslips?(?:\s+for)?|show\s+|^)\s*([A-Z][A-Za-z\s'.-]{2,50}?)(?:'s|\s+payslip|\s+last|\s+this|\s+cost|\s*$)",
    re.I,
)


def _query_blob(message: str, intent: Intent) -> str:
    return f"{message} {intent.specific_intent} {intent.subject_area}".lower().replace("_", " ")


def is_payroll_orchestration_query(message: str, intent: Intent) -> bool:
    """True when the question should use payroll models, not generic HR employee reads."""
    blob = _query_blob(message, intent)
    if intent.subject_area == "payroll":
        return True
    if _LABOR_COST_RE.search(blob):
        return True
    if any(token in blob for token in _PAYROLL_SUBJECT_TOKENS):
        return True
    if "hr.payslip" in blob or "cost.allocation" in blob:
        return True
    if "most expensive project" in blob or "labor cost trend" in blob:
        return True
    if "average labor cost" in blob or "average labour cost" in blob:
        return True
    msg = message.lower()
    if "across projects" in msg and ("cost" in msg or "labor" in msg or "labour" in msg):
        return True
    return False


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


def _temporal(context: ContextStack | None):
    if context is not None and context.temporal_context is not None:
        return context.temporal_context
    from gateway.core.temporal_context import TemporalContext

    return TemporalContext.build()


def _payslip_date_domain(message: str, intent: Intent, context: ContextStack | None) -> list[Any]:
    from gateway.core.strategy_planner import resolve_report_date_range

    temporal = _temporal(context)
    date_from, date_to = resolve_report_date_range(_query_blob(message, intent), temporal)
    return [["date_from", ">=", date_from], ["date_to", "<=", date_to]]


def _default_payroll_month_year(temporal) -> tuple[str, str]:
    """Latest closed payroll month (before the 20th, use previous calendar month)."""
    month = temporal.today.month
    year = temporal.today.year
    if temporal.today.day <= 20:
        if month == 1:
            month, year = 12, year - 1
        else:
            month -= 1
    return str(month), str(year)


def _allocation_month_year(
    message: str,
    intent: Intent,
    context: ContextStack | None,
) -> tuple[str | None, str | None, list[Any]]:
    """Return (month, year, extra domain) for hr.payslip.cost.allocation."""
    msg = message.lower()
    temporal = _temporal(context)
    domain: list[Any] = []

    if "last 6 months" in msg or "last six months" in msg:
        return None, None, []

    if "this year" in msg or "year to date" in msg:
        domain.append(["year", "=", str(temporal.today.year)])
        return None, str(temporal.today.year), domain

    if "last month" in msg:
        prev = temporal.today.replace(day=1) - timedelta(days=1)
        return str(prev.month), str(prev.year), domain

    if "this month" in msg or "current month" in msg:
        month, year = _default_payroll_month_year(temporal)
        return month, year, domain

    month, year = _default_payroll_month_year(temporal)
    return month, year, domain


def _employee_name_hint(message: str) -> str:
    match = _EMPLOYEE_NAME_RE.search(message.strip())
    if match:
        name = match.group(1).strip(" '\"")
        if name.lower() not in ("draft", "finalized", "total", "payroll", "payslips"):
            return name
    if "'s" in message:
        return message.split("'s")[0].strip()
    return ""


def resolve_payroll_tool(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_name, payload) for payroll queries, or None if not payroll-routed."""
    if not is_payroll_orchestration_query(message, intent):
        return None

    blob = _query_blob(message, intent)
    msg = message.lower()
    project_id = _confirmed_project_id(context)
    employee_hint = _employee_name_hint(message)

    if employee_hint and "across projects" in msg:
        year = str(_temporal(context).today.year)
        if "this year" in msg or "year to date" in msg:
            emp_domain: list[Any] = [["year", "=", year]]
        else:
            month, yr, period_domain = _allocation_month_year(message, intent, context)
            emp_domain = list(period_domain)
            if month and yr:
                emp_domain.extend([["month", "=", month], ["year", "=", yr]])
        emp_domain.append(["employee_id.name", "ilike", employee_hint.split()[0]])
        return "aggregate_odoo", {
            "model": COST_ALLOCATION_MODEL,
            "domain": emp_domain,
            "group_by": ["project_id"],
            "aggregates": ["amount:sum"],
            "limit": 50,
        }

    # --- Category E: cost.allocation flagship queries ---
    if _LABOR_COST_RE.search(blob) or "cost allocation" in blob or "labor cost trend" in blob:
        month, year, period_domain = _allocation_month_year(message, intent, context)
        domain: list[Any] = list(period_domain)
        if project_id is not None:
            domain.append(["project_id", "=", project_id])

        if "most expensive" in blob or "top project" in blob:
            year_only = str(_temporal(context).today.year)
            if "this year" in blob:
                domain = [["year", "=", year_only]]
            return "aggregate_odoo", {
                "model": COST_ALLOCATION_MODEL,
                "domain": domain or [["year", "=", year_only]],
                "group_by": ["project_id"],
                "aggregates": ["amount:sum"],
                "limit": 20,
            }

        if "average labor cost" in blob or "average labour cost" in blob:
            return "aggregate_odoo", {
                "model": COST_ALLOCATION_MODEL,
                "domain": domain or [["year", "=", str(_temporal(context).today.year)]],
                "group_by": ["project_id"],
                "aggregates": ["amount:avg"],
                "limit": 50,
            }

        if project_id is not None:
            if month and year and "last 6 months" not in msg and "trend" not in msg:
                domain.extend([["month", "=", month], ["year", "=", year]])
            if "trend" in msg or "last 6 months" in msg:
                return "aggregate_odoo", {
                    "model": COST_ALLOCATION_MODEL,
                    "domain": domain,
                    "group_by": ["month", "year"],
                    "aggregates": ["amount:sum"],
                    "limit": 24,
                }
            if "breakdown" in msg or "by employee" in msg:
                return "aggregate_odoo", {
                    "model": COST_ALLOCATION_MODEL,
                    "domain": domain,
                    "group_by": ["employee_id"],
                    "aggregates": ["amount:sum"],
                    "limit": 100,
                }
            return "aggregate_odoo", {
                "model": COST_ALLOCATION_MODEL,
                "domain": domain,
                "group_by": ["project_id"],
                "aggregates": ["amount:sum"],
                "limit": 10,
            }

    # --- Category D: worked days ---
    if any(token in blob for token in ("job mission", "worked days", "annual leave salary", "sick leave usage")):
        wd_domain: list[Any] = []
        if "this year" in blob or "year to date" in blob:
            wd_domain.extend(_payslip_date_domain(message, intent, context))
        if "job mission" in blob:
            wd_domain.append(["code", "=", "JM"])
            return "aggregate_odoo", {
                "model": WORKED_DAYS_MODEL,
                "domain": wd_domain,
                "group_by": ["code"],
                "aggregates": ["number_of_hours:sum"],
                "limit": 10,
            }
        if "annual leave salary" in blob:
            wd_domain.append(["code", "=", "ANNUAL"])
            return "aggregate_odoo", {
                "model": WORKED_DAYS_MODEL,
                "domain": wd_domain,
                "group_by": ["code"],
                "aggregates": ["amount:sum"],
                "limit": 10,
            }
        if "sick leave usage" in blob:
            wd_domain.append(["code", "in", ["SL_FULL", "SL_HALF", "SL_UNPAID"]])
            return "query_odoo", {
                "model": WORKED_DAYS_MODEL,
                "domain": wd_domain,
                "fields": ["employee_id", "code", "number_of_days", "number_of_hours", "amount"],
                "limit": 50,
                "order": "number_of_days desc",
            }

    # --- Category C: deductions ---
    if any(token in blob for token in ("fine", "fines", "advance", "advances", "deduction")):
        ps_domain = _payslip_date_domain(message, intent, context)
        if "fine" in blob:
            return "aggregate_odoo", {
                "model": "hr.payslip",
                "domain": ps_domain,
                "group_by": ["state"],
                "aggregates": ["fine:sum"],
                "limit": 10,
            }
        if "advance" in blob and ("pending" in blob or "who has" in blob):
            return "query_odoo", {
                "model": "hr.payslip",
                "domain": ps_domain + [["advance", ">", 0]],
                "fields": ["name", "employee_id", "advance", "date_from", "date_to", "state"],
                "limit": 50,
                "order": "advance desc",
            }
        if "highest deduction" in blob or "highest deductions" in blob:
            return "query_odoo", {
                "model": "hr.payslip",
                "domain": ps_domain,
                "fields": ["name", "employee_id", "total_deductions", "fine", "advance", "date_to"],
                "limit": 20,
                "order": "total_deductions asc",
            }
        if "average deduction" in blob:
            return "aggregate_odoo", {
                "model": "hr.payslip",
                "domain": ps_domain,
                "group_by": ["employee_id"],
                "aggregates": ["total_deductions:avg"],
                "limit": 50,
            }

    # --- Category B: aggregate payroll ---
    if "total payroll cost" in blob or "payroll by department" in blob:
        ps_domain = _payslip_date_domain(message, intent, context)
        if "by department" in blob:
            return "aggregate_odoo", {
                "model": "hr.payslip",
                "domain": ps_domain,
                "group_by": ["employee_id"],
                "aggregates": ["net_salary:sum"],
                "limit": 100,
            }
        return "aggregate_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain,
            "group_by": ["state"],
            "aggregates": ["net_salary:sum"],
            "limit": 10,
        }

    if "labor vs staff payroll" in blob or ("labor" in blob and "staff" in blob and "payroll" in blob):
        ps_domain = _payslip_date_domain(message, intent, context)
        return "aggregate_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain,
            "group_by": ["state"],
            "aggregates": ["labor_snapshot_total_salary:sum", "staff_snapshot_total_salary:sum"],
            "limit": 10,
        }

    if "overtime cost" in blob or "overtime" in blob and "cost" in blob:
        ps_domain = _payslip_date_domain(message, intent, context)
        return "aggregate_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain,
            "group_by": ["state"],
            "aggregates": ["total_over_time:sum"],
            "limit": 10,
        }

    if "sick leave cost" in blob:
        ps_domain = _payslip_date_domain(message, intent, context)
        return "aggregate_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain,
            "group_by": ["state"],
            "aggregates": [
                "sick_leave_full_paid_amount:sum",
                "sick_leave_half_paid_amount:sum",
                "sick_leave_unpaid_amount:sum",
            ],
            "limit": 10,
        }

    # --- Category A: payslip basics ---
    if "draft payslip" in blob and "count" in blob:
        return "aggregate_odoo", {
            "model": "hr.payslip",
            "domain": [["state", "=", "draft"]],
            "group_by": ["state"],
            "aggregates": ["id:count"],
            "limit": 5,
        }

    if "finalized payslip" in blob or ("finalized" in blob and "payslip" in blob):
        ps_domain = _payslip_date_domain(message, intent, context)
        return "query_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain + [["state", "in", ["verify", "finance", "paid"]]],
            "fields": ["name", "employee_id", "state", "date_from", "date_to", "net_salary"],
            "limit": 50,
            "order": "date_to desc",
        }

    if "payslip" in blob and "batch" in blob:
        batch_hint = message.split("for")[-1].strip() if " for " in message.lower() else message
        return "query_odoo", {
            "model": "hr.payslip",
            "domain": [["payslip_run_id.name", "ilike", batch_hint[:60]]],
            "fields": ["name", "employee_id", "state", "date_from", "date_to", "net_salary"],
            "limit": 50,
            "order": "date_to desc",
        }

    if "payslip" in blob:
        ps_domain: list[Any] = []
        if "last month" in blob or "this month" in blob or "this year" in blob:
            ps_domain = _payslip_date_domain(message, intent, context)
        if employee_hint:
            ps_domain.append(["employee_id.name", "ilike", employee_hint.split()[0]])
        return "query_odoo", {
            "model": "hr.payslip",
            "domain": ps_domain,
            "fields": [
                "name",
                "number",
                "employee_id",
                "net_salary",
                "labor_snapshot_total_salary",
                "staff_snapshot_total_salary",
                "date_from",
                "date_to",
                "state",
            ],
            "limit": 50,
            "order": "date_to desc",
        }

    return None

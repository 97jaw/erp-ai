"""Deterministic payroll query routing for open-gate universal tools (Phase M6).

Maps payroll / labor-cost questions to query_odoo / aggregate_odoo payloads
without new Odoo tools.
"""

from __future__ import annotations

import re
import calendar
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
_EMPLOYEE_FILE_ID_RE = re.compile(r"^\s*(\d{3,6})\s*$")
_NAME_AFTER_FOR_RE = re.compile(
    r"\bfor\s+([A-Za-z][A-Za-z\s'.-]{1,60}?)(?:\s*$|\s*,|\s+in\b|\s+last\b|\s+this\b|\s+may\b|\s+jun\b|\s+jul\b|\s+aug\b|\s+sep\b|\s+oct\b|\s+nov\b|\s+dec\b|\s+jan\b|\s+feb\b|\s+mar\b|\s+apr\b)",
    re.I,
)
_PAYSLIP_NAME_RE = re.compile(
    r"\bpayslips?\s+(?:for\s+)?([A-Za-z][A-Za-z\s'.-]{2,50}?)(?:\s+payslip|\s+salary|\s*$)",
    re.I,
)
_BLOCKED_NAME_TOKENS = frozenset(
    {
        "need",
        "show",
        "get",
        "want",
        "give",
        "payslip",
        "payslips",
        "salary",
        "payroll",
        "expense",
        "expenses",
        "project",
        "for",
        "me",
        "the",
        "this",
        "last",
        "month",
        "year",
        "labor",
        "labour",
        "villa",
        "maintenance",
        "cost",
        "costs",
        "draft",
        "finalized",
        "total",
    },
)
_NON_PAYROLL_MARKERS = (
    "project expense",
    "project expenses",
    "expenses for",
    "expense of",
    "expenses of",
    "expense for",
    "p&l",
    "profit and loss",
    "balance sheet",
    "trial balance",
    "general ledger",
    "invoice",
    "receivable",
    "purchase order",
    "national guard",
    "show me project",
    "cost of project",
)
_MONTH_YEAR_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s*,?\s*(\d{4})\b",
    re.I,
)
_MONTH_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _query_blob(message: str, intent: Intent) -> str:
    return f"{message} {intent.specific_intent} {intent.subject_area}".lower().replace("_", " ")


def _active_payroll_context(context: ContextStack | None) -> bool:
    """True when the prior turn was payroll/HR and this message is likely a follow-up."""
    if context is None:
        return False
    facts = context.working_memory.session_facts or {}
    pending = facts.get("pending_entity_clarification") or {}
    if pending.get("payroll_context"):
        return True
    last = facts.get("last_turn") or {}
    if last.get("domain") == "payroll":
        return True
    if last.get("subject_area") in {"payroll", "hr"}:
        last_msg = str(last.get("message") or "").lower()
        if any(token in last_msg for token in _PAYROLL_SUBJECT_TOKENS):
            return True
        if "payslip" in last_msg or "salary" in last_msg:
            return True
    return False


def _looks_like_employee_name_fragment(message: str) -> bool:
    """Heuristic: two+ name tokens, not a project/cost query."""
    cleaned = _MONTH_YEAR_RE.sub("", message).strip(" ,")
    lowered = cleaned.lower()
    if any(
        token in lowered
        for token in (
            "villa",
            "maintenance",
            "project",
            "invoice",
            "p&l",
            "profit",
            "client",
            "terminated",
            "termination",
            "how many",
            "headcount",
            "department",
            "request",
            "requests",
            "attendance",
            "visa",
        )
    ):
        return False
    tokens = [token for token in re.split(r"[\s,]+", cleaned) if len(token) > 1]
    return len(tokens) >= 2


def message_has_payroll_period(message: str) -> bool:
    """Return True when the user named an explicit month/year or relative payroll period."""
    blob = message.lower()
    if _MONTH_YEAR_RE.search(blob):
        return True
    return any(
        token in blob
        for token in (
            "last month",
            "this month",
            "this year",
            "last quarter",
            "ytd",
            "year to date",
        )
    )


def is_explicit_non_payroll_query(message: str) -> bool:
    """True when the message is clearly about project/financial data, not payroll."""
    lowered = message.lower()
    if any(marker in lowered for marker in _NON_PAYROLL_MARKERS):
        return True
    if "expense" in lowered and "project" in lowered:
        return True
    return False


def extract_employee_file_id(message: str) -> str | None:
    """Return employee File ID from bare numeric or inline 'file id NNNN' messages."""
    from gateway.core.hr_payroll_composer import extract_inline_file_id

    return extract_inline_file_id(message)


def is_payroll_file_id_follow_up(message: str, context: ContextStack | None) -> bool:
    """True when a numeric-only reply is answering a prior payslip clarification."""
    if extract_employee_file_id(message) is None:
        return False
    if context is None:
        return False
    facts = context.working_memory.session_facts or {}
    pending = facts.get("pending_entity_clarification") or {}
    if pending.get("payroll_context"):
        return True
    last = facts.get("last_turn") or {}
    if last.get("domain") == "payroll":
        return True
    last_msg = str(last.get("message") or "").lower()
    return any(token in last_msg for token in ("payslip", "salary", "payroll"))


def should_block_project_entity_search(message: str, context: ContextStack | None) -> bool:
    """Prevent project WO search when user supplied an employee File ID in payroll context."""
    return is_payroll_file_id_follow_up(message, context)


def is_payroll_orchestration_query(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> bool:
    """True when the question should use payroll models, not generic HR employee reads."""
    from gateway.core.hr_payroll_composer import is_hr_request_query, is_separation_count_query

    if is_separation_count_query(message, intent) or is_hr_request_query(message, intent):
        return False

    if is_explicit_non_payroll_query(message):
        return False

    blob = _query_blob(message, intent)
    if intent.subject_area == "payroll":
        return True
    if is_payroll_file_id_follow_up(message, context):
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
    if message_has_payroll_period(message) and _employee_name_hint(message):
        return True
    if message_has_payroll_period(message) and _looks_like_employee_name_fragment(message) and any(
        token in blob
        for token in ("payslip", "payslips", "salary", "payroll", "deduction", "overtime", "net salary")
    ):
        return True
    if context is not None and _active_payroll_context(context):
        if is_explicit_non_payroll_query(message):
            return False
        if extract_employee_file_id(message):
            return True
        if any(token in blob for token in _PAYROLL_SUBJECT_TOKENS):
            return True
        if _employee_name_hint(message):
            return True
        if message_has_payroll_period(message) and _looks_like_employee_name_fragment(message):
            return True
    return False


def looks_like_project_cost_only(message: str) -> bool:
    lowered = message.lower()
    return bool(_LABOR_COST_RE.search(lowered)) and any(
        token in lowered for token in ("villa", "maintenance", "project", "wo ")
    )


def requires_payroll_project_confirmation(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> bool:
    """True when a named-project labor-cost query needs project pick before payroll tools."""
    if not is_payroll_orchestration_query(message, intent, context):
        return False
    if _confirmed_project_id(context) is not None:
        return False
    if looks_like_project_cost_only(message):
        return True
    from gateway.core.project_query_utils import (
        extract_project_name_hint,
        extract_project_number_hint,
    )

    if _LABOR_COST_RE.search(message.lower()) and (
        extract_project_name_hint(message) or extract_project_number_hint(message)
    ):
        return True
    return False


def confirmed_project_id(context: ContextStack | None) -> int | None:
    """Public accessor for the active confirmed project id in session facts."""
    return _confirmed_project_id(context)


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


def _parse_month_year(message: str) -> tuple[str, str] | None:
    match = _MONTH_YEAR_RE.search(message.lower())
    if not match:
        return None
    month_key = match.group(1)[:3].lower()
    month_num = _MONTH_NUM.get(month_key)
    if not month_num:
        return None
    return str(month_num), str(match.group(2))


def _clean_name_candidate(raw: str) -> str:
    """Normalize and validate a extracted employee name fragment."""
    name = " ".join(str(raw or "").strip(" '\"").split())
    if not name or len(name) < 2:
        return ""
    tokens = [token for token in name.split() if token]
    if not tokens:
        return ""
    if all(token.lower() in _BLOCKED_NAME_TOKENS for token in tokens):
        return ""
    if tokens[0].lower() in _BLOCKED_NAME_TOKENS:
        return ""
    if any(token.lower() in {"expense", "expenses", "project", "invoice", "guard"} for token in tokens):
        return ""
    return name


def _employee_name_hint(message: str) -> str:
    from gateway.core.hr_payroll_composer import extract_employee_name

    return extract_employee_name(message)


def _payslip_period_payload(
    message: str,
    context: ContextStack | None = None,
) -> dict[str, str]:
    """Optional date bounds for get_employee_payslips filtering in synthesis."""
    month_year = _parse_month_year(message)
    if not month_year and context is not None:
        from gateway.core.hr_payroll_composer import parse_period_window

        period = parse_period_window(message, context)
        if period:
            return {
                "date_from": period.date_from,
                "date_to": period.date_to,
            }
        pending = context.working_memory.session_facts.get("pending_entity_clarification") or {}
        prior_query = str(pending.get("query") or "")
        last_turn = context.working_memory.session_facts.get("last_turn") or {}
        month_year = _parse_month_year(prior_query) or _parse_month_year(
            str(last_turn.get("message") or ""),
        )
    if not month_year:
        return {}
    month, year = month_year
    last_day = calendar.monthrange(int(year), int(month))[1]
    return {
        "date_from": f"{year}-{int(month):02d}-01",
        "date_to": f"{year}-{int(month):02d}-{last_day:02d}",
    }


def _resolve_payslip_by_file_id(
    message: str,
    context: ContextStack | None,
) -> tuple[str, dict[str, Any]] | None:
    """Route numeric File ID replies to payslip detail with period inheritance."""
    file_id = extract_employee_file_id(message)
    if not file_id:
        return None
    if not (
        is_payroll_file_id_follow_up(message, context)
        or "payslip" in message.lower()
        or "salary" in message.lower()
    ):
        if context is None or not _active_payroll_context(context):
            return None
    from gateway.core.hr_payroll_composer import resolve_payroll_subtype

    payload: dict[str, Any] = {
        "employee_file_id": file_id,
        "detail_type": "header",
    }
    subtype = resolve_payroll_subtype(message, context)
    if subtype == "payslip_lines":
        payload["detail_type"] = "lines"
    elif subtype == "payslip_distribution":
        payload["detail_type"] = "distribution"
    payload.update(_payslip_period_payload(message, context))
    return "get_payslip_detail", payload


def resolve_payroll_tool(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_name, payload) for payroll queries, or None if not payroll-routed."""
    if not is_payroll_orchestration_query(message, intent, context):
        return None

    from gateway.core.hr_payroll_composer import compose_payroll_plan, plan_to_route

    composer_plan = compose_payroll_plan(message, intent, context)
    if composer_plan is not None:
        routed = plan_to_route(composer_plan)
        if routed is not None:
            return routed

    file_id_route = _resolve_payslip_by_file_id(message, context)
    if file_id_route is not None:
        return file_id_route

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

        # Named-project labor cost must go through entity confirmation first.
        if requires_payroll_project_confirmation(message, intent, context):
            return None

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

    if not _LABOR_COST_RE.search(blob) and (
        "payslip" in blob
        or (
            employee_hint
            and (message_has_payroll_period(message) or _active_payroll_context(context))
        )
    ):
        from gateway.core.hr_payroll_composer import (
            build_employee_name_domain,
            payslip_period_domain_from_dates,
        )

        ps_domain: list[Any] = []
        month_year = _parse_month_year(message)
        if month_year:
            month, year = month_year
            last_day = calendar.monthrange(int(year), int(month))[1]
            ps_domain = payslip_period_domain_from_dates(
                f"{year}-{int(month):02d}-01",
                f"{year}-{int(month):02d}-{last_day:02d}",
            )
        elif "last month" in blob or "this month" in blob or "this year" in blob:
            from gateway.core.strategy_planner import resolve_report_date_range

            temporal = _temporal(context)
            date_from, date_to = resolve_report_date_range(blob, temporal)
            ps_domain = payslip_period_domain_from_dates(date_from, date_to)
        if employee_hint:
            name_domain = build_employee_name_domain(employee_hint)
            if ps_domain:
                ps_domain = ["&"] + name_domain + ps_domain
            else:
                ps_domain = name_domain
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
                "fine",
                "advance",
                "total_deductions",
            ],
            "limit": 1 if ps_domain else 50,
            "order": "date_to desc",
        }

    return None

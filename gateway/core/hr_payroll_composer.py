"""Unified HR/Payroll query composer — slot filling, routing plans, session context.

Covers models documented in hr_module_context.py and payroll_module_context.py:
  hr.employee, hr.department, hr.attendance, employee.request, request.type,
  hr.payslip, hr.payslip.line, hr.payslip.worked_days, hr.payslip.cost.allocation,
  hr.payslip.run, hr.contract (via query_odoo when needed).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

COST_ALLOCATION_MODEL = "hr.payslip.cost.allocation"
WORKED_DAYS_MODEL = "hr.payslip.worked_days"

_FILLER_PREFIX_RE = re.compile(
    r"^(?:its|it's|yes|no|actually|i mean|that's|that is|he is|she is|correct|sorry)\s+",
    re.I,
)
_INLINE_FILE_ID_RE = re.compile(
    r"\b(?:file\s*id|emp(?:loyee)?\s*id|emp_id)\s*[:\s]?\s*(\d{3,6})\b",
    re.I,
)
_BARE_FILE_ID_RE = re.compile(r"^\s*(\d{3,6})\s*$")
_MONTH_YEAR_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|r?may|jun(?:e)?|jul(?:y)?|"
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
_NAME_AFTER_FOR_RE = re.compile(
    r"\b(?:for|of)\s+([A-Za-z][A-Za-z\s'.-]{1,60}?)"
    r"(?:\s*$|\s*,|\s+in\b|\s+last\b|\s+this\b|\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|\s+\d{4})",
    re.I,
)
_REQUEST_FOR_RE = re.compile(
    r"\b(?:employee\s+)?requests?\s+(?:for|of)\s+([A-Za-z][A-Za-z\s'.-]{1,60}?)(?:\s*$|\s*,|\s+in\b|\s+last\b|\s+this\b)",
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
        "of",
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
        "distribution",
        "calculation",
        "file",
        "id",
        "recent",
        "employee",
        "request",
        "requests",
        "pending",
        "approved",
        "leave",
        "loan",
        "transfer",
        "transfers",
        "resignation",
        "termination",
        "clearance",
        "unresolved",
        "who",
        "has",
    },
)
_SEPARATION_TOKENS = (
    "terminated",
    "termination",
    "terminations",
    "fired",
    "clearance",
    "separation",
    "separations",
)
_REQUEST_TYPE_MAP: list[tuple[tuple[str, ...], str]] = [
    (("leave request", "leave requests", "pending leave", "on leave"), "leave"),
    (("resignation", "resignations", "resign"), "resign"),
    (("termination", "terminated", "terminations", "fired"), "termination"),
    (("clearance",), "clearance"),
    (("promotion", "promotions"), "promotion"),
    (("loan", "advance salary", "advance_salary"), "loan"),
    (("transfer", "transfers"), "transfer"),
    (("passport request", "passport"), "passport"),
    (("sim card", "sim_card"), "sim"),
    (("certificate", "salary certificate"), "certificate"),
]


@dataclass
class PeriodWindow:
    """Resolved date bounds for payslip or HR request queries."""

    date_from: str
    date_to: str
    label: str = ""


@dataclass
class HRPayrollQueryPlan:
    """Deterministic execution plan for an HR or payroll turn."""

    domain: str
    subtype: str
    tool: str
    tool_input: dict[str, Any] = field(default_factory=dict)
    employee_file_id: str | None = None
    employee_name_hint: str | None = None
    period: PeriodWindow | None = None
    request_type: str | None = None
    needs_clarification: list[str] = field(default_factory=list)
    clarification_question: str | None = None


def strip_conversational_filler(message: str) -> str:
    """Remove leading conversational prefixes from name-correction follow-ups."""
    cleaned = (message or "").strip()
    while True:
        next_clean = _FILLER_PREFIX_RE.sub("", cleaned).strip()
        if next_clean == cleaned:
            break
        cleaned = next_clean
    return cleaned


def normalize_month_typos(message: str) -> str:
    """Fix common month typos before period parsing."""
    text = message or ""
    text = re.sub(r"\brmay\b", "may", text, flags=re.I)
    text = re.sub(r"\bmayy\b", "may", text, flags=re.I)
    return text


def extract_inline_file_id(message: str) -> str | None:
    """Extract file id from inline phrases like 'file id 2721'."""
    match = _INLINE_FILE_ID_RE.search(message or "")
    if match:
        return match.group(1)
    bare = _BARE_FILE_ID_RE.match((message or "").strip())
    if bare:
        return bare.group(1)
    return None


def _clean_name_candidate(raw: str) -> str:
    name = " ".join(str(raw or "").strip(" '\"").split())
    if not name or len(name) < 2:
        return ""
    tokens = name.split()
    if all(token.lower() in _BLOCKED_NAME_TOKENS for token in tokens):
        return ""
    if tokens[0].lower() in _BLOCKED_NAME_TOKENS:
        return ""
    if any(token.lower() in {"expense", "expenses", "project", "invoice", "guard"} for token in tokens):
        return ""
    return name


def extract_employee_name(message: str) -> str:
    """Extract employee name from payroll or HR request phrasing."""
    cleaned = normalize_month_typos(strip_conversational_filler(message))
    cleaned = _MONTH_YEAR_RE.sub("", cleaned).strip(" ,")
    lowered = cleaned.lower()
    if any(
        token in lowered
        for token in ("labor cost", "labour cost", "cost allocation", "villa maintenance", "villa no")
    ):
        return ""

    if any(
        token in lowered
        for token in (
            "who has",
            "who is",
            "unresolved",
            "pending leave",
            "pending request",
        )
    ):
        return ""

    for pattern in (_REQUEST_FOR_RE, _NAME_AFTER_FOR_RE):
        match = pattern.search(cleaned)
        if match:
            candidate = _clean_name_candidate(match.group(1))
            if candidate:
                return candidate

    payslip_match = re.search(
        r"\bpayslips?\s+(?:for\s+)?([A-Za-z][A-Za-z\s'.-]{2,50}?)(?:\s+payslip|\s+salary|\s+distribution|\s+calculation|\s*$)",
        cleaned,
        re.I,
    )
    if payslip_match:
        candidate = _clean_name_candidate(payslip_match.group(1))
        if candidate:
            return candidate

    leading_before_period = _MONTH_YEAR_RE.split(cleaned)[0].strip(" ,")
    if leading_before_period:
        candidate = _clean_name_candidate(leading_before_period)
        if candidate:
            return candidate

    if "'s" in cleaned:
        candidate = _clean_name_candidate(cleaned.split("'s")[0])
        if candidate:
            return candidate

    return ""


def build_employee_name_domain(name_hint: str) -> list[Any]:
    """Multi-token ilike domain for hr.payslip / employee.request employee_id.name."""
    parts = [part for part in name_hint.split() if len(part) > 1]
    if not parts:
        return []
    domain: list[Any] = [["employee_id.name", "ilike", parts[0]]]
    if len(parts) > 1:
        domain.append(["employee_id.name", "ilike", parts[-1]])
    return domain


def build_employee_name_domain_hr_employee(name_hint: str) -> list[Any]:
    """Name domain for hr.employee direct queries."""
    parts = [part for part in name_hint.split() if len(part) > 1]
    if not parts:
        return []
    domain: list[Any] = [["name", "ilike", parts[0]]]
    if len(parts) > 1:
        domain.append(["name", "ilike", parts[-1]])
    return domain


def _parse_month_year(message: str) -> tuple[int, int] | None:
    match = _MONTH_YEAR_RE.search(normalize_month_typos(message))
    if not match:
        return None
    month_key = match.group(1).lower()[:3]
    if month_key.startswith("rm"):
        month_key = "may"
    month = _MONTH_NUM.get(month_key)
    if not month:
        return None
    return month, int(match.group(2))


def parse_period_window(
    message: str,
    context: ContextStack | None = None,
    *,
    default_recent_months: int = 3,
) -> PeriodWindow | None:
    """Resolve explicit or relative period from message and session."""
    normalized = normalize_month_typos(message)
    month_year = _parse_month_year(normalized)
    if month_year:
        month, year = month_year
        last_day = calendar.monthrange(year, month)[1]
        month_name = calendar.month_name[month]
        return PeriodWindow(
            date_from=f"{year}-{month:02d}-01",
            date_to=f"{year}-{month:02d}-{last_day:02d}",
            label=f"{month_name} {year}",
        )

    blob = normalized.lower()
    temporal = context.temporal_context if context else None
    if temporal is None:
        from gateway.core.temporal_context import TemporalContext

        temporal = TemporalContext.build()
    today = temporal.today

    if "this month" in blob:
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        return PeriodWindow(
            date_from=first.isoformat(),
            date_to=end.isoformat(),
            label="this month",
        )
    if "last month" in blob:
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return PeriodWindow(
            date_from=first_prev.isoformat(),
            date_to=last_prev.isoformat(),
            label="last month",
        )
    if "this year" in blob:
        return PeriodWindow(
            date_from=f"{today.year}-01-01",
            date_to=f"{today.year}-12-31",
            label=f"{today.year}",
        )
    if "recent" in blob or "latest" in blob:
        start = today - timedelta(days=default_recent_months * 31)
        return PeriodWindow(
            date_from=start.isoformat(),
            date_to=today.isoformat(),
            label=f"last {default_recent_months} months",
        )

    if context is not None:
        pending = get_pending_hr_context(context)
        prior = str(pending.get("prior_query") or "")
        resolved_period = pending.get("resolved") or {}
        if resolved_period.get("date_from") and resolved_period.get("date_to"):
            return PeriodWindow(
                date_from=str(resolved_period["date_from"]),
                date_to=str(resolved_period["date_to"]),
                label=str(resolved_period.get("label") or ""),
            )
        inherited = parse_period_window(prior, None)
        if inherited:
            return inherited
        last_turn = context.working_memory.session_facts.get("last_turn") or {}
        inherited = parse_period_window(str(last_turn.get("message") or ""), None)
        if inherited:
            return inherited

    return None


def map_request_type(message: str) -> str | None:
    """Map user tokens to employee.request request_type filter."""
    blob = message.lower()
    for tokens, mapped in _REQUEST_TYPE_MAP:
        if any(token in blob for token in tokens):
            return mapped
    return None


def get_pending_hr_context(context: ContextStack | None) -> dict[str, Any]:
    """Return unified pending HR/payroll clarification context."""
    if context is None:
        return {}
    facts = context.working_memory.session_facts or {}
    pending = facts.get("pending_hr_context") or {}
    if pending:
        return dict(pending)
    legacy = facts.get("pending_entity_clarification") or {}
    if legacy.get("payroll_context"):
        return {
            "domain": "payroll",
            "subtype": "payslip_header",
            "prior_query": legacy.get("query") or "",
            "awaiting": ["employee"],
            "resolved": {},
        }
    return {}


def merge_pending_hr_context(
    context: ContextStack | None,
    message: str,
) -> dict[str, Any]:
    """Merge session pending context with current message slots."""
    pending = get_pending_hr_context(context)
    if not pending:
        return {}

    resolved = dict(pending.get("resolved") or {})
    file_id = extract_inline_file_id(message)
    if file_id:
        resolved["employee_file_id"] = file_id
    name = extract_employee_name(message)
    if name:
        resolved["employee_name_hint"] = name
    period = parse_period_window(message, context)
    if period:
        resolved["date_from"] = period.date_from
        resolved["date_to"] = period.date_to
        resolved["label"] = period.label

    merged = dict(pending)
    merged["resolved"] = resolved
    return merged


def classify_payroll_subtype(message: str) -> str:
    """Classify payroll query detail level."""
    blob = message.lower()
    if "payslip" in blob and "distribution" in blob:
        return "payslip_distribution"
    if any(
        token in blob
        for token in (
            "salary calculation",
            "salary breakdown",
            "payslip line",
            "payslip lines",
            "deduction",
            "deductions",
            "overtime breakdown",
            "net salary",
            "gross salary",
            "breakdown",
        )
    ):
        return "payslip_lines"
    if any(token in blob for token in ("worked days", "worked_days", "job mission")):
        return "payslip_worked_days"
    return "payslip_header"


def is_separation_count_query(message: str, intent: Intent) -> bool:
    blob = f"{message} {intent.specific_intent}".lower()
    if not any(token in blob for token in _SEPARATION_TOKENS):
        return False
    return any(token in blob for token in ("how many", "count", "number of", "total"))


def is_hr_request_query(message: str, intent: Intent) -> bool:
    blob = f"{message} {intent.specific_intent}".lower()
    if any(token in blob for token in ("transfer", "transfers", "unresolved request", "pending leave")):
        if not extract_employee_name(message) and not extract_inline_file_id(message):
            return False
    broad = any(
        phrase in blob
        for phrase in (
            "employee request",
            "employee requests",
            "hr request",
            "hr requests",
            "requests for",
            "request for",
            "recent request",
            "recent requests",
        )
    ) or ("request" in blob and "employee" in blob and "for" in blob)
    if not broad:
        if intent.subject_area == "hr" and "request" in blob and extract_employee_name(message):
            return True
        return False
    if extract_employee_name(message) or extract_inline_file_id(message):
        return True
    if "recent" in blob and "request" in blob:
        return True
    if any(phrase in blob for phrase in ("requests for", "request for", "employee request")):
        return True
    return False


def compose_payroll_plan(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> HRPayrollQueryPlan | None:
    """Build a payroll execution plan when composer can handle the query."""
    blob = f"{message} {intent.specific_intent}".lower()
    pending = merge_pending_hr_context(context, message)
    pending_ctx = get_pending_hr_context(context)
    payroll_follow_up = pending_ctx.get("domain") == "payroll" or pending.get("domain") == "payroll"

    if not payroll_follow_up and not any(
        token in blob
        for token in (
            "payslip",
            "payslips",
            "salary slip",
            "salary calculation",
            "salary breakdown",
            "deduction",
            "payroll",
        )
    ):
        return None

    resolved = pending.get("resolved") or {}
    subtype = pending.get("subtype") or pending_ctx.get("subtype") or classify_payroll_subtype(
        str(pending.get("prior_query") or pending_ctx.get("prior_query") or message)
    )

    file_id = extract_inline_file_id(message) or resolved.get("employee_file_id")
    name_hint = extract_employee_name(message) or resolved.get("employee_name_hint")
    period = parse_period_window(message, context)

    tool_input: dict[str, Any] = {}
    if file_id:
        tool_input["employee_file_id"] = str(file_id)
    if name_hint:
        tool_input["employee_name"] = name_hint
    if period:
        tool_input["date_from"] = period.date_from
        tool_input["date_to"] = period.date_to

    if subtype in {"payslip_lines", "payslip_distribution"}:
        tool_input["detail_type"] = "lines" if subtype == "payslip_lines" else "distribution"
        if not file_id and not name_hint:
            return HRPayrollQueryPlan(
                domain="payroll",
                subtype=subtype,
                tool="get_payslip_detail",
                tool_input=tool_input,
                needs_clarification=["employee"],
                clarification_question=(
                    "Whose payslip should I show — employee name or file ID?"
                ),
            )
        return HRPayrollQueryPlan(
            domain="payroll",
            subtype=subtype,
            tool="get_payslip_detail",
            tool_input=tool_input,
            employee_file_id=str(file_id) if file_id else None,
            employee_name_hint=name_hint,
            period=period,
        )

    if file_id:
        payload: dict[str, Any] = {"employee_file_id": str(file_id), "limit": 20}
        if period:
            payload["date_from"] = period.date_from
            payload["date_to"] = period.date_to
        return HRPayrollQueryPlan(
            domain="payroll",
            subtype="payslip_header",
            tool="get_employee_payslips",
            tool_input=payload,
            employee_file_id=str(file_id),
            period=period,
        )

    if name_hint:
        ps_domain: list[Any] = build_employee_name_domain(name_hint)
        if period:
            month_year = _parse_month_year(normalize_month_typos(message))
            if month_year:
                month, year = month_year
                ps_domain.append(["date_from", ">=", f"{year}-{month:02d}-01"])
                last_day = calendar.monthrange(year, month)[1]
                ps_domain.append(["date_to", "<=", f"{year}-{month:02d}-{last_day:02d}"])
            else:
                ps_domain.append(["date_from", ">=", period.date_from])
                ps_domain.append(["date_to", "<=", period.date_to])
        return HRPayrollQueryPlan(
            domain="payroll",
            subtype="payslip_header",
            tool="query_odoo",
            tool_input={
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
                "limit": 10,
                "order": "date_to desc",
            },
            employee_name_hint=name_hint,
            period=period,
        )

    return None


def compose_hr_request_plan(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> HRPayrollQueryPlan | None:
    """Build employee.request plan with person, type, and date slots."""
    if not is_hr_request_query(message, intent):
        return None

    pending = merge_pending_hr_context(context, message)
    resolved = pending.get("resolved") or {}
    file_id = extract_inline_file_id(message) or resolved.get("employee_file_id")
    name_hint = extract_employee_name(message) or resolved.get("employee_name_hint")
    request_type = map_request_type(message) or resolved.get("request_type")
    period = parse_period_window(message, context)
    if period is None:
        temporal = context.temporal_context if context else None
        if temporal is None:
            from gateway.core.temporal_context import TemporalContext

            temporal = TemporalContext.build()
        start = temporal.today - timedelta(days=93)
        period = PeriodWindow(
            date_from=start.isoformat(),
            date_to=temporal.today.isoformat(),
            label="last 3 months",
        )

    tool_input: dict[str, Any] = {
        "date_from": period.date_from,
        "date_to": period.date_to,
        "limit": 50,
    }
    if file_id:
        tool_input["employee_file_id"] = str(file_id)
    if name_hint:
        tool_input["employee_name"] = name_hint
    if request_type:
        tool_input["request_type"] = request_type
    blob = message.lower()
    if "pending" in blob or "unresolved" in blob:
        tool_input["status"] = "pending"
    elif "approved" in blob:
        tool_input["status"] = "approved"

    return HRPayrollQueryPlan(
        domain="hr",
        subtype="hr_request_list",
        tool="list_employee_requests",
        tool_input=tool_input,
        employee_file_id=str(file_id) if file_id else None,
        employee_name_hint=name_hint,
        period=period,
        request_type=request_type,
    )


def compose_separation_plan(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> HRPayrollQueryPlan | None:
    """Count terminations/separations via employee.request."""
    if not is_separation_count_query(message, intent):
        return None

    period = parse_period_window(message, context)
    if period is None:
        temporal = context.temporal_context if context else None
        if temporal is None:
            from gateway.core.temporal_context import TemporalContext

            temporal = TemporalContext.build()
        today = temporal.today
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        period = PeriodWindow(
            date_from=first.isoformat(),
            date_to=today.replace(day=last_day).isoformat(),
            label="this month",
        )

    blob = message.lower()
    request_type = "termination"
    if "resign" in blob and "termin" not in blob:
        request_type = "resign"
    elif "clearance" in blob:
        request_type = "clearance"

    domain: list[Any] = [
        ["request_type", "ilike", request_type],
        ["create_date", ">=", period.date_from],
        ["create_date", "<=", period.date_to],
    ]
    if "approved" in blob:
        domain.append(["is_approve", "=", True])

    group_by: list[str] = []
    if "department" in blob or "by department" in blob:
        group_by = ["employee_id.department_id"]

    if group_by:
        return HRPayrollQueryPlan(
            domain="hr",
            subtype="separation_count",
            tool="aggregate_odoo",
            tool_input={
                "model": "employee.request",
                "domain": domain,
                "group_by": group_by,
                "aggregates": ["id:count"],
                "limit": 200,
            },
            period=period,
            request_type=request_type,
        )

    return HRPayrollQueryPlan(
        domain="hr",
        subtype="separation_count",
        tool="aggregate_odoo",
        tool_input={
            "model": "employee.request",
            "domain": domain,
            "group_by": [],
            "aggregates": ["id:count"],
            "limit": 1,
        },
        period=period,
        request_type=request_type,
    )


def plan_to_route(plan: HRPayrollQueryPlan) -> tuple[str, dict[str, Any]] | None:
    """Convert plan to handler route tuple when ready to execute."""
    if plan.needs_clarification:
        return None
    return plan.tool, dict(plan.tool_input)

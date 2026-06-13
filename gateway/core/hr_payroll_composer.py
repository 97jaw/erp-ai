"""Unified HR/Payroll query composer — slot filling, routing plans, session context.

Covers models documented in hr_module_context.py and payroll_module_context.py:
  hr.employee, hr.department, hr.attendance, employee.requests, request.type,
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
EMPLOYEE_REQUESTS_MODEL = "employee.requests"

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
_REQUEST_ID_RE = re.compile(
    r"\b(?:request\s*(?:id|#|number|no\.?)?|req(?:uest)?\s*#?)\s*[:#-]?\s*(\d{1,8})\b",
    re.I,
)
_REQUEST_NAME_RE = re.compile(
    r"\b((?:REQ|ER|HR)[-/][A-Za-z0-9/-]{3,40})\b",
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


def extract_request_reference(message: str) -> tuple[int | None, str | None]:
    """Extract numeric request id or reference code from user text."""
    text = message or ""
    id_match = _REQUEST_ID_RE.search(text)
    if id_match:
        try:
            return int(id_match.group(1)), None
        except ValueError:
            pass
    name_match = _REQUEST_NAME_RE.search(text)
    if name_match:
        return None, name_match.group(1).strip()
    stripped = text.strip()
    if re.fullmatch(r"\d{1,8}", stripped):
        return int(stripped), None
    return None, None


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


def build_payslip_period_domain(month: int, year: int) -> list[Any]:
    """Match Elrace payroll month by slip name (May-2026) or calendar overlap."""
    last_day = calendar.monthrange(year, month)[1]
    first_day = f"{year}-{month:02d}-01"
    last_day_str = f"{year}-{month:02d}-{last_day:02d}"
    name_pattern = f"{calendar.month_abbr[month]}-{year}"
    return [
        "|",
        ["name", "ilike", name_pattern],
        "&",
        ["date_from", "<=", last_day_str],
        ["date_to", ">=", first_day],
    ]


def payslip_period_domain_from_dates(date_from: str, date_to: str) -> list[Any]:
    """Build payslip period domain from calendar month bounds (YYYY-MM-DD)."""
    try:
        year = int(str(date_from)[:4])
        month = int(str(date_from)[5:7])
    except (ValueError, IndexError):
        return [
            "&",
            ["date_from", "<=", date_to],
            ["date_to", ">=", date_from],
        ]
    return build_payslip_period_domain(month, year)


def build_employee_name_domain(name_hint: str) -> list[Any]:
    """Multi-token ilike domain for hr.payslip / employee.requests employee_id.name."""
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
    """Map user tokens to employee.requests request_type_id.name filter."""
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
    blob = normalize_month_typos(message).lower()
    if "payslip" in blob and "distribution" in blob:
        return "payslip_distribution"
    if any(token in blob for token in ("worked days", "worked_days", "worked day", "job mission")):
        return "payslip_worked_days"
    if "basic" in blob and any(token in blob for token in ("salary", "payslip", "slip", "payroll")):
        return "payslip_lines_basic"
    if any(token in blob for token in ("deduction", "deductions", "fine", "advance", "late")):
        if any(token in blob for token in ("payslip", "salary", "payroll", "slip", "breakdown")):
            return "payslip_lines_deductions"
    if any(
        token in blob
        for token in ("overtime", "over time", " ot ", "overtime breakdown", "wot", "normal ot")
    ):
        if any(token in blob for token in ("payslip", "salary", "payroll", "slip", "breakdown")):
            return "payslip_lines_overtime"
    if any(
        token in blob
        for token in (
            "salary calculation",
            "salary breakdown",
            "payslip line",
            "payslip lines",
            "overtime breakdown",
            "gross salary",
            "breakdown",
            "computation",
        )
    ):
        return "payslip_full"
    if any(
        token in blob
        for token in (
            "deduction",
            "deductions",
            "net salary",
        )
    ):
        return "payslip_full"
    if "calculation" in blob or "computation" in blob:
        if any(
            token in blob
            for token in ("salary", "payroll", "payslip", "slip", "file id", "emp_id", "emp id")
        ) or extract_inline_file_id(message):
            return "payslip_full"
        if re.search(r"\b(?:s)?alary\b", blob):
            return "payslip_full"
    return "payslip_header"


def classify_payslip_line_filter(message: str) -> str | None:
    """Detect payslip line sub-filter from drill-down phrasing."""
    blob = normalize_month_typos(message).lower()
    if "basic" in blob and any(token in blob for token in ("salary", "payslip", "slip", "payroll")):
        return "basic"
    if any(token in blob for token in ("deduction", "deductions", "fine", "advance", "late")):
        return "deductions"
    if any(token in blob for token in ("overtime", "over time", " ot ", "wot", "normal ot", "weekend ot")):
        return "overtime"
    return None


def is_payslip_drill_down_query(message: str, context: ContextStack | None) -> bool:
    """True when a payslip session follow-up asks for lines, OT, deductions, etc."""
    pending = get_pending_hr_context(context)
    if pending.get("domain") != "payroll":
        return False
    blob = normalize_month_typos(message).lower()
    if classify_payslip_line_filter(message):
        return True
    if classify_payroll_subtype(message) != "payslip_header":
        return True
    drill_tokens = (
        "breakdown",
        "line",
        "lines",
        "allowance",
        "worked",
        "attendance",
        "computation",
        "calculation",
    )
    return any(token in blob for token in drill_tokens)


def map_subtype_to_detail_tool_input(subtype: str) -> dict[str, str]:
    """Map composer subtype to get_payslip_detail parameters."""
    if subtype == "payslip_header":
        return {"detail_type": "header"}
    if subtype == "payslip_distribution":
        return {"detail_type": "distribution"}
    if subtype == "payslip_worked_days":
        return {"detail_type": "worked_days"}
    if subtype == "payslip_lines_basic":
        return {"detail_type": "lines", "line_filter": "basic"}
    if subtype == "payslip_lines_deductions":
        return {"detail_type": "lines", "line_filter": "deductions"}
    if subtype == "payslip_lines_overtime":
        return {"detail_type": "lines", "line_filter": "overtime"}
    return {"detail_type": "full"}


_PAYSLIP_DETAIL_SUBTYPES = frozenset(
    {
        "payslip_header",
        "payslip_lines",
        "payslip_full",
        "payslip_distribution",
        "payslip_worked_days",
        "payslip_lines_basic",
        "payslip_lines_deductions",
        "payslip_lines_overtime",
    }
)


def resolve_payroll_subtype(
    message: str,
    context: ContextStack | None = None,
) -> str:
    """Resolve detail subtype from message and session (inherits prior payslip intent)."""
    pending = merge_pending_hr_context(context, message) if context else {}
    pending_ctx = get_pending_hr_context(context)
    stored = pending.get("subtype") or pending_ctx.get("subtype")
    line_filter = classify_payslip_line_filter(message)
    if line_filter == "basic":
        return "payslip_lines_basic"
    if line_filter == "deductions":
        return "payslip_lines_deductions"
    if line_filter == "overtime":
        return "payslip_lines_overtime"
    from_message = classify_payroll_subtype(message)
    if from_message != "payslip_header":
        return from_message
    if stored and stored != "payslip_header":
        return str(stored)
    prior = str(pending.get("prior_query") or pending_ctx.get("prior_query") or "")
    from_prior = classify_payroll_subtype(prior)
    if from_prior != "payslip_header":
        return from_prior
    return str(stored or from_message or "payslip_header")


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


def is_hr_request_detail_query(message: str, context: ContextStack | None = None) -> bool:
    """True when the user asks for validation, approval chain, or leave dates on a request."""
    blob = f"{message}".lower()
    pending = get_pending_hr_context(context)
    detail_tokens = (
        "validation",
        "approval",
        "approver",
        "approval chain",
        "leave date",
        "leave dates",
        "leave duration",
        "leave period",
        "request detail",
        "request details",
        "status of request",
        "who approved",
        "pending approval",
        "validation status",
    )
    request_id, request_name = extract_request_reference(message)
    if request_id is not None or request_name:
        return True
    if any(token in blob for token in detail_tokens):
        return "request" in blob or pending.get("domain") == "hr"
    if pending.get("domain") == "hr" and re.fullmatch(r"\d{1,8}", (message or "").strip()):
        return True
    return False


def compose_hr_request_detail_plan(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> HRPayrollQueryPlan | None:
    """Build get_employee_request_detail plan for drill-down on one request."""
    if not is_hr_request_detail_query(message, context):
        return None

    pending = merge_pending_hr_context(context, message)
    resolved = pending.get("resolved") or {}
    request_id, request_name = extract_request_reference(message)
    if request_id is None and not request_name:
        recent_ids = resolved.get("recent_request_ids") or []
        if recent_ids:
            request_id = int(recent_ids[0])

    tool_input: dict[str, Any] = {}
    if request_id is not None:
        tool_input["request_id"] = int(request_id)
    if request_name:
        tool_input["request_name"] = request_name
    file_id = extract_inline_file_id(message) or resolved.get("employee_file_id")
    name_hint = extract_employee_name(message) or resolved.get("employee_name_hint")
    if file_id:
        tool_input["employee_file_id"] = str(file_id)
    if name_hint:
        tool_input["employee_name"] = name_hint

    if not tool_input.get("request_id") and not tool_input.get("request_name"):
        return HRPayrollQueryPlan(
            domain="hr",
            subtype="hr_request_detail",
            tool="get_employee_request_detail",
            tool_input=tool_input,
            needs_clarification=["request"],
            clarification_question="Which request should I open — request ID or reference?",
        )

    return HRPayrollQueryPlan(
        domain="hr",
        subtype="hr_request_detail",
        tool="get_employee_request_detail",
        tool_input=tool_input,
        employee_file_id=str(file_id) if file_id else None,
        employee_name_hint=name_hint,
    )


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

    if not payroll_follow_up and not is_payslip_drill_down_query(message, context) and not any(
        token in blob
        for token in (
            "payslip",
            "payslips",
            "salary slip",
            "salary calculation",
            "salary breakdown",
            "deduction",
            "payroll",
            "calculation",
            "breakdown",
            "overtime",
            "worked day",
            "worked days",
            "basic salary",
        )
    ) and not (
        "calculation" in blob and (extract_inline_file_id(message) or "file id" in blob)
    ):
        return None

    resolved = pending.get("resolved") or {}
    subtype = resolve_payroll_subtype(message, context)

    file_id = extract_inline_file_id(message) or resolved.get("employee_file_id")
    name_hint = extract_employee_name(message) or resolved.get("employee_name_hint")
    period = parse_period_window(message, context)
    if payroll_follow_up or is_payslip_drill_down_query(message, context):
        if not file_id:
            file_id = resolved.get("employee_file_id")
        if not name_hint:
            name_hint = resolved.get("employee_name_hint")

    tool_input: dict[str, Any] = {}
    if file_id:
        tool_input["employee_file_id"] = str(file_id)
    if name_hint:
        tool_input["employee_name"] = name_hint
    if period:
        tool_input["date_from"] = period.date_from
        tool_input["date_to"] = period.date_to

    if subtype in _PAYSLIP_DETAIL_SUBTYPES or is_payslip_drill_down_query(message, context):
        tool_input.update(map_subtype_to_detail_tool_input(subtype))
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

    return None


def compose_hr_request_plan(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> HRPayrollQueryPlan | None:
    """Build employee.requests plan with person, type, and date slots."""
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
    """Count terminations/separations via employee.requests."""
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
        ["request_type_id.name", "ilike", request_type],
        ["create_date", ">=", period.date_from],
        ["create_date", "<=", f"{period.date_to} 23:59:59"],
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
                "model": EMPLOYEE_REQUESTS_MODEL,
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
            "model": EMPLOYEE_REQUESTS_MODEL,
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

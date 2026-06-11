"""Detect project header/profile queries and route them to get_project_profile.

Project Model Phase 1. Profile queries read project.project header fields
directly (no Deep Think): budget allocations (engineer/trade amounts, W.O
distribution), team assignments, schedule, status, progress, identity, audit.
Actual computed spend (expenses, GL breakdown, P&L) stays in Deep Think.
"""

from __future__ import annotations

import re

# Queries about ACTUAL spend / computed financials — never profile.
_SPEND_DISQUALIFIER_RE = re.compile(
    r"\b("
    r"expenses?|expenditures?|spen[dt]\w*|breakdown|break\s+down|"
    r"p\s*&\s*l|profit\s+(and|&)\s+loss|revenue|ledger|\bgl\b|"
    r"trial\s+balance|balance\s+sheet|cash\s*flow|"
    r"petty\s+cash|timesheets?|purchase\s+orders?|invoices?|payments?|"
    r"over\s+budget|costs?\b"
    r")\b"
    r"|مصروف|مصاريف|تكلفة|تكاليف|إيراد|ايراد",
    re.IGNORECASE,
)

# Header AMOUNT allocations (the W.O Amount Distribution block + role amounts).
_AMOUNT_SIGNAL_RE = re.compile(
    r"(engineer|engineers|eng|civil|mechanical|electrical|ict|it|plumb\w*|"
    r"branch\s+manager|project\s+manager)\s*('?s)?\s+amounts?"
    r"|amounts?\s+distribution|w\.?\s*o\.?\s+distribution"
    r"|\bw\.?\s*o\.?\s+amount|wo_amount|work\s+order\s+amount"
    r"|estimation\s+amount|extended\s+amount",
    re.IGNORECASE,
)

# Single named engineering trade + "amount" -> answer just that discipline.
_SINGLE_TRADE_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("civil", re.compile(r"\bcivil\s+(eng\w*\s+)?amounts?\b", re.IGNORECASE)),
    ("electrical", re.compile(r"\belectrical\s+(eng\w*\s+)?amounts?\b", re.IGNORECASE)),
    ("mechanical", re.compile(r"\bmechanical\s+(eng\w*\s+)?amounts?\b", re.IGNORECASE)),
    ("ict", re.compile(r"\b(ict|it)\s+(eng\w*\s+)?amounts?\b", re.IGNORECASE)),
)

# Generic "engineer(s)/engineering amount" -> the four disciplines only.
_ENGINEERS_AMOUNT_RE = re.compile(
    r"\beng(ineer(s|ing)?)?\s*('?s)?\s+amounts?\b",
    re.IGNORECASE,
)

# Explicit "distribution" -> the full W.O breakdown block.
_DISTRIBUTION_RE = re.compile(r"distribution", re.IGNORECASE)

# "w.o amount" / "work order amount" on its own -> just the single W.O Amount.
_WO_AMOUNT_RE = re.compile(
    r"\bw\.?\s*o\.?\s+amounts?\b|\bwo_amount\b|work\s+order\s+amounts?",
    re.IGNORECASE,
)

# "estimation amount" on its own -> just the estimation figure.
_ESTIMATION_AMOUNT_RE = re.compile(r"estimation\s+amounts?", re.IGNORECASE)

# Require a role/team keyword — bare "who is …" matches general knowledge (e.g. UAE leadership).
_TEAM_ROLE = (
    r"project\s+manager|projects\s+manager|branch\s+manager|"
    r"civil(?:\s+engineer)?|mechanical(?:\s+engineer)?|"
    r"electrical(?:\s+engineer)?|ict(?:\s+engineer)?|it(?:\s+engineer)?|"
    r"plumber|architect|document\s+controller|supervisors?|\bpm\b"
)
_TEAM_SIGNAL_RE = re.compile(
    rf"\bwho\s+is\s+(?:the\s+)?(?:{_TEAM_ROLE})|"
    rf"\bwho'?s\s+(?:the\s+)?(?:{_TEAM_ROLE})|"
    rf"\bwho\s+manages\b|"
    rf"{_TEAM_ROLE}|"
    r"team\s+(of|for|on)|assigned\s+to",
    re.IGNORECASE,
)

_SCHEDULE_SIGNAL_RE = re.compile(
    r"start\s+date|end\s+date|expir\w+\s+date|completion\s+date|"
    r"\bdeadline\b|due\s+date|\bduration\b|extend\w*\s+(date|duration)|"
    r"how\s+long|pending\s+days",
    re.IGNORECASE,
)

_STATUS_SIGNAL_RE = re.compile(
    r"\bstatus\b|\bstage\b|\bprogress\b|\bactive\b|in\s+progress|"
    r"complete[d]?\b|delayed",
    re.IGNORECASE,
)

_IDENTITY_SIGNAL_RE = re.compile(
    r"wo\s*(ref|number|#)|w\.?\s*o\.?\s*(ref|number|#)|project\s+code|"
    r"contract\s+(no|number)|agreement\b|client\s+(of|for|name)|"
    r"customer\s+(of|for|name)|\blocation\b|\bcity\b|arabic\s+name|"
    r"last\s+updated|updated\s+by|created\s+by|created\s+on",
    re.IGNORECASE,
)

_PROJECT_CONTEXT_RE = re.compile(
    r"\bproject\b|\bvilla\b|\bschool\b|\bmaintenance\b|\bwo\b|work\s+order"
    r"|مشروع|فيلا|مدرسة|صيانة",
    re.IGNORECASE,
)


def has_project_context(message: str) -> bool:
    """True when the message contains project-ish wording worth resolving."""
    return bool(_PROJECT_CONTEXT_RE.search(message or ""))


def is_project_profile_text(message: str) -> bool:
    """Text-only profile detection (no Intent needed) — used by the Deep Think
    eligibility carve-out and the handler routing."""
    text = (message or "").strip()
    if len(text) < 4:
        return False
    if _SPEND_DISQUALIFIER_RE.search(text):
        return False
    has_signal = bool(
        _AMOUNT_SIGNAL_RE.search(text)
        or _TEAM_SIGNAL_RE.search(text)
        or _SCHEDULE_SIGNAL_RE.search(text)
        or _IDENTITY_SIGNAL_RE.search(text)
        or _STATUS_SIGNAL_RE.search(text),
    )
    if not has_signal:
        return False
    # Avoid hijacking generic questions: require some project context wording
    # unless the signal is amount/team-specific (those are unambiguous).
    if _AMOUNT_SIGNAL_RE.search(text) or _TEAM_SIGNAL_RE.search(text):
        return True
    return bool(_PROJECT_CONTEXT_RE.search(text))


def is_project_profile_query(message: str, intent) -> bool:
    """Profile detection with intent context."""
    if getattr(intent, "out_of_scope", False):
        return False
    if is_project_profile_text(message):
        return True
    # Follow-ups like "who manages it" — active project supplies context.
    if getattr(intent, "subject_area", "") == "project_attribute":
        return True
    return False


def derive_profile_focus(message: str) -> str:
    """Map the question wording to the profile section it asks about."""
    text = (message or "")
    for trade, pattern in _SINGLE_TRADE_RES:
        if pattern.search(text):
            return trade
    if _ENGINEERS_AMOUNT_RE.search(text):
        return "engineers"
    # "distribution" wording asks for the whole breakdown; a bare "w.o amount"
    # or "estimation amount" asks for just that single figure.
    if not _DISTRIBUTION_RE.search(text):
        if _WO_AMOUNT_RE.search(text):
            return "wo_amount"
        if _ESTIMATION_AMOUNT_RE.search(text):
            return "estimation"
    if _AMOUNT_SIGNAL_RE.search(text):
        return "amounts"
    if _TEAM_SIGNAL_RE.search(text):
        return "team"
    if _SCHEDULE_SIGNAL_RE.search(text):
        return "schedule"
    if _STATUS_SIGNAL_RE.search(text):
        return "status"
    if _IDENTITY_SIGNAL_RE.search(text):
        return "identity"
    return "all"

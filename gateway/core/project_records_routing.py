"""Detect project record-list queries and route them to get_project_records.

Project Model Phase 2. Record-list queries (invoices, LPO invoices, purchase
orders, timesheets, petty cash, staff, supervisors of a project) read the
linked Odoo models directly in normal mode — no Deep Think. Aggregated
financial analysis (expense summary/breakdown, P&L) stays in Deep Think.
"""

from __future__ import annotations

import re

# Aggregation/analysis wording that keeps the query in the Deep Think /
# expense lanes even when a record keyword appears.
_ANALYSIS_DISQUALIFIER_RE = re.compile(
    r"\b("
    r"breakdown|break\s+down|drill\s*down|"
    r"p\s*&\s*l|profit\s+(and|&)\s+loss|trial\s+balance|balance\s+sheet|"
    r"cash\s*flow|ledger|\bgl\b|"
    r"compare|comparison|versus|\bvs\b|"
    r"over\s+budget|spend\s+percent"
    r")\b",
    re.IGNORECASE,
)

# Ordered: first match wins. More specific phrasings come first (e.g.
# "lpo invoices" before "purchase orders"/"lpo", "petty cash sheets"
# before "petty cash", "client invoices" before "invoices").
_RECORD_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("client_invoices", re.compile(
        r"client\s+invoices?|customer\s+invoices?|sales\s+invoices?"
        r"|فواتير\s+العميل|فواتير\s+العملاء",
        re.IGNORECASE,
    )),
    ("lpo_invoices", re.compile(
        r"lpo\s+invoices?|vendor\s+(bills?|invoices?)|supplier\s+(bills?|invoices?)"
        r"|purchase\s+invoices?|\bbills\b"
        r"|فواتير\s+المورد|فواتير\s+الموردين",
        re.IGNORECASE,
    )),
    ("invoices", re.compile(r"\binvoices?\b|فاتورة|فواتير", re.IGNORECASE)),
    ("purchase_orders", re.compile(
        r"purchase\s+orders?|\bpos\b|\bp\.?o\.?s?\b(?!\w)|\blpos?\b"
        r"|أوامر\s+الشراء|امر\s+شراء",
        re.IGNORECASE,
    )),
    ("timesheets", re.compile(
        r"time\s*sheets?|timesheets?|سجل\s+الدوام|الدوام",
        re.IGNORECASE,
    )),
    ("petty_cash_sheets", re.compile(
        r"petty\s+cash\s+(sheets?|vouchers?|reports?)",
        re.IGNORECASE,
    )),
    ("petty_cash", re.compile(r"petty\s+cash|نثرية|النثرية", re.IGNORECASE)),
    ("supervisors", re.compile(r"supervisors?|مشرف|مشرفين", re.IGNORECASE)),
    ("staff", re.compile(
        r"staff\s*(list|members)?|workers?\s+(list|on\s+site)|labou?rers?"
        r"|\bmanpower\b|قائمة\s+الموظفين|العمال",
        re.IGNORECASE,
    )),
)

# Leading "<records keyword> of/for" qualifier — strip before extracting the
# project name (mirrors the amount-qualifier stripping in
# project_query_utils._LEADING_AMOUNT_QUALIFIER_RE).
_LEADING_RECORDS_QUALIFIER_RE = re.compile(
    r"^\s*(?:show\s+(?:me\s+)?|list\s+|give\s+me\s+|get\s+me?\s*|tell\s+me\s+)?"
    r"(?:all\s+|the\s+|latest\s+|recent\s+)*"
    r"(?:client\s+|customer\s+|sales\s+|lpo\s+|vendor\s+|supplier\s+|purchase\s+)?"
    r"(?:invoices?|bills?|orders?|timesheets?|time\s*sheets?|"
    r"petty\s+cash(?:\s+(?:sheets?|vouchers?|reports?|expenses?))?|"
    r"staff(?:\s+list|\s+members)?|supervisors?|workers?(?:\s+list)?|manpower)"
    r"\s+(?:of|for|on|linked\s+to)\s+",
    re.IGNORECASE,
)


def derive_record_type(message: str) -> str | None:
    """Map the question wording to a record_type, or None when no match."""
    text = message or ""
    for record_type, pattern in _RECORD_TYPE_PATTERNS:
        if pattern.search(text):
            return record_type
    return None


def records_disqualified(message: str) -> bool:
    """True when analysis/aggregation wording should keep the query off this lane."""
    return bool(_ANALYSIS_DISQUALIFIER_RE.search(message or ""))


def is_project_records_text(message: str) -> bool:
    """Text-only record-list detection — used by the Deep Think carve-out
    and the handler routing."""
    text = (message or "").strip()
    if len(text) < 4:
        return False
    if _ANALYSIS_DISQUALIFIER_RE.search(text):
        return False
    record_type = derive_record_type(text)
    if record_type is None:
        return False
    from gateway.core.project_profile_routing import has_project_context

    # Require project wording or an explicit "of/for <name>" so we don't
    # hijack global queries like "show me all invoices".
    if has_project_context(text):
        return True
    return bool(_LEADING_RECORDS_QUALIFIER_RE.search(text))


def is_project_records_query(message: str, intent) -> bool:
    """Record-list detection with intent context."""
    del intent
    return is_project_records_text(message)


def extract_records_project_hint(message: str) -> str | None:
    """Project name fragment for a records query ('invoices of X' -> 'X')."""
    from gateway.core.project_query_utils import extract_project_name_hint

    text = (message or "").strip()
    stripped = _LEADING_RECORDS_QUALIFIER_RE.sub("", text, count=1)
    if stripped and stripped != text:
        return extract_project_name_hint(stripped)
    return extract_project_name_hint(text)

"""Pre-response clarification helpers (QUERY_RESPONSE_INTELLIGENCE Phase 5)."""
from __future__ import annotations

import json
import re
from typing import Any

_CLARIFY_BLOCK_RE = re.compile(r"<clarify>\s*([\s\S]*?)\s*</clarify>", re.IGNORECASE)

_FINANCIAL_QUERY_RE = re.compile(
    r"\b("
    r"p\s*&\s*l|profit\s+and\s+loss|profit\s*&\s*loss|trial\s+balance|"
    r"balance\s+sheet|general\s+ledger|financial\s+report|revenue|expenses?|"
    r"income\s+statement|أرباح|خسائر|ميزان|تقرير\s+مالي"
    r")\b",
    re.IGNORECASE,
)

_DATE_IN_QUERY_RE = re.compile(
    r"\b("
    r"this\s+month|last\s+month|this\s+year|last\s+year|ytd|year\s+to\s+date|"
    r"last\s+\d+\s+(?:days?|months?|weeks?)|past\s+\d+\s+months?|"
    r"q[1-4]|quarter|january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*,?\s*\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"from\s+\d|to\s+\d|between\s+\d|"
    r"هذا\s+الشهر|الشهر\s+الماضي|هذا\s+العام|آخر\s+\d+|"
    r"من\s+\d|إلى\s+\d|للفترة"
    r")\b",
    re.IGNORECASE,
)

_SKIP_CLARIFY_RE = re.compile(
    r"\b(skip|default|use\s+default|any\s+period|all\s+time)\b|تخطي",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank\s+you|مرحبا|السلام|شكرا)\b",
    re.IGNORECASE,
)


def parse_clarify_block(text: str = "") -> dict[str, Any] | None:
    if not text:
        return None
    match = _CLARIFY_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def strip_clarify_markup(text: str = "") -> str:
    cleaned = _CLARIFY_BLOCK_RE.sub("", text or "")
    cleaned = re.sub(r"</clarify>\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def should_offer_date_clarification(message: str = "") -> bool:
    text = (message or "").strip()
    if not text or len(text) < 2:
        return False
    if _GREETING_RE.search(text):
        return False
    if _SKIP_CLARIFY_RE.search(text):
        return False
    if not _FINANCIAL_QUERY_RE.search(text):
        return False
    from gateway.core.project_query_utils import (
        extract_project_name_hint,
        looks_like_project_cost_query,
    )

    if looks_like_project_cost_query(text) and extract_project_name_hint(text):
        return False
    from gateway.core.payroll_query_routing import message_has_payroll_period

    if message_has_payroll_period(text):
        return False
    if _DATE_IN_QUERY_RE.search(text):
        return False
    return True


def build_date_range_clarification(language: str = "en") -> dict[str, Any]:
    arabic = language == "ar"
    return {
        "reason": "date_range_missing",
        "question": (
            "Which time period would you like for this report?"
            if not arabic
            else "أي فترة زمنية تريد لهذا التقرير؟"
        ),
        "question_ar": "أي فترة زمنية تريد لهذا التقرير؟",
        "options": [
            {
                "id": "this_month",
                "label": "This Month",
                "label_ar": "هذا الشهر",
                "query_suffix": " for this month",
            },
            {
                "id": "last_3m",
                "label": "Last 3 Months",
                "label_ar": "آخر 3 أشهر",
                "query_suffix": " for the last 3 months",
                "is_default": True,
            },
            {
                "id": "ytd",
                "label": "This Year",
                "label_ar": "هذا العام",
                "query_suffix": " for this year",
            },
            {
                "id": "custom",
                "label": "Custom Range",
                "label_ar": "نطاق مخصص",
                "action": "open_date_picker",
            },
        ],
        "skip_option": {
            "label": "Skip (use last 3 months)",
            "label_ar": "تخطي (آخر 3 أشهر)",
            "query_suffix": " for the last 3 months",
        },
    }


def build_deep_think_date_clarification(
    message: str,
    temporal: Any,
    language: str = "en",
) -> dict[str, Any]:
    """Clickable period card for company-wide report queries in normal mode.

    Every option carries explicit dates and `deep_think: True` so a single click
    resumes the query straight into Deep Think and fetches real Odoo figures.
    Explicit `from X to Y` suffixes win over any period phrase already in the
    message, so conflicting wording can never change the fetched range.
    """
    from gateway.core.strategy_planner import resolve_report_date_range

    arabic = language == "ar"
    today = temporal.today
    this_month = (today.replace(day=1).isoformat(), today.isoformat())
    presets = [
        ("this_month", "This Month", "هذا الشهر", this_month),
        ("last_month", "Last Month", "الشهر الماضي", tuple(temporal.last_month)),
        ("last_3m", "Last 3 Months", "آخر 3 أشهر", tuple(temporal.last_3_months)),
        ("ytd", "This Year", "هذا العام", tuple(temporal.ytd)),
        ("last_year", "Last Year", "العام الماضي", tuple(temporal.last_year)),
    ]
    detected = tuple(resolve_report_date_range(message, temporal))

    options: list[dict[str, Any]] = []
    for option_id, label, label_ar, date_range in presets:
        option: dict[str, Any] = {
            "id": option_id,
            "label": label,
            "label_ar": label_ar,
            "query_suffix": f" from {date_range[0]} to {date_range[1]}",
            "deep_think": True,
        }
        if date_range == detected:
            option["is_default"] = True
        options.append(option)
    options.append(
        {
            "id": "custom",
            "label": "Custom Range",
            "label_ar": "نطاق مخصص",
            "action": "open_date_picker",
            "deep_think": True,
        },
    )

    return {
        "reason": "date_range_deep_think",
        "resume_deep_think": True,
        "question": (
            "Which period should I pull this report for? "
            "Pick one and I'll fetch the actual figures from Odoo."
            if not arabic
            else "أي فترة تريد لهذا التقرير؟ اختر واحدة وسأجلب الأرقام الفعلية من أودو."
        ),
        "question_ar": "أي فترة تريد لهذا التقرير؟ اختر واحدة وسأجلب الأرقام الفعلية من أودو.",
        "options": options,
        "skip_option": {
            "label": "Use detected period",
            "label_ar": "استخدام الفترة المكتشفة",
            "query_suffix": f" from {detected[0]} to {detected[1]}",
            "deep_think": True,
        },
    }


def enrich_query_with_clarification(original_query: str, option: dict[str, Any]) -> str:
    suffix = str(option.get("query_suffix") or "")
    if not suffix.strip():
        return original_query.strip()
    if suffix.strip().lower() in original_query.lower():
        return original_query.strip()
    return f"{original_query.strip()}{suffix}"

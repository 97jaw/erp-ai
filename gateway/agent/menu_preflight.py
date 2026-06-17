"""Deterministic menu navigation — avoid Claude re-showing the welcome picker."""

from __future__ import annotations

import re
from typing import Any

from gateway.agent.preflight_blocks import PreflightResult, date_quick_block, pill_block
from gateway.agent.session_entities import (
    get_entities,
    has_financial_date_range,
    update_entities,
)
from gateway.clarify import _DATE_IN_QUERY_RE

_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF]",
    re.UNICODE,
)
_PICK_SEGMENT_RE = re.compile(r"\s*—\s*")

_FINANCIAL_CATEGORY_RE = re.compile(r"\bfinancial\s+reports?\b", re.I)

# --- Top-level module pick detectors ---
_PROJECTS_PICK_RE = re.compile(r"^projects?\s*(?:&|and)?\s*costs?$", re.I)
_HR_PICK_RE = re.compile(r"^hr\s*(?:&|and)?\s*employees?$", re.I)
_PAYROLL_PICK_RE = re.compile(r"^payroll\s*(?:&|and)?\s*payslips?$", re.I)
_PROCUREMENT_PICK_RE = re.compile(r"^procurement\s*(?:&|and)?\s*lpos?$", re.I)
_FLEET_PICK_RE = re.compile(r"^fleet\s*(?:&|and)?\s*vehicles?$", re.I)
_RECEIVABLES_PICK_RE = re.compile(r"^receivables?\s*(?:&|and)?\s*ar$", re.I)
_SEARCH_PICK_RE = re.compile(r"^search\s*/\s*ask\s+anything$", re.I)

_PROJECTS_OPTIONS: list[dict[str, str]] = [
    {"id": "Show active projects", "label": "Show active projects", "icon": "🏗️"},
    {"id": "Show project expense summary", "label": "Show project expense summary", "icon": "💰"},
    {"id": "Top projects by expense", "label": "Top projects by expense", "icon": "📊"},
    {"id": "Projects with cost overrun", "label": "Projects with cost overrun", "icon": "⚠️"},
]

_HR_OPTIONS: list[dict[str, str]] = [
    {"id": "Show employees by department", "label": "Show employees by department", "icon": "👥"},
    {"id": "How many employees do we have", "label": "How many employees do we have", "icon": "🔢"},
    {"id": "Show department headcount", "label": "Show department headcount", "icon": "📋"},
    {"id": "Search an employee by name", "label": "Search an employee by name", "icon": "🔍"},
]

_PAYROLL_OPTIONS: list[dict[str, str]] = [
    {"id": "Show my payslip", "label": "Show my payslip", "icon": "💳"},
    {"id": "Show payroll summary last month", "label": "Show payroll summary last month", "icon": "📅"},
    {"id": "Show recent payslips", "label": "Show recent payslips", "icon": "📄"},
    {"id": "Check payslip by file ID", "label": "Check payslip by file ID", "icon": "🔍"},
]

_PROCUREMENT_OPTIONS: list[dict[str, str]] = [
    {"id": "Show recent purchase orders", "label": "Show recent purchase orders", "icon": "📋"},
    {"id": "Show LPOs pending approval", "label": "Show LPOs pending approval", "icon": "⏳"},
    {"id": "LPO summary this month", "label": "LPO summary this month", "icon": "📊"},
    {"id": "Search LPO by vendor", "label": "Search LPO by vendor", "icon": "🔍"},
]

_FLEET_OPTIONS: list[dict[str, str]] = [
    {"id": "Show all fleet vehicles", "label": "Show all fleet vehicles", "icon": "🚗"},
    {"id": "Search vehicle by employee", "label": "Search vehicle by employee", "icon": "🔍"},
    {"id": "Show vehicles by status", "label": "Show vehicles by status", "icon": "📋"},
    {"id": "Vehicles with expiring insurance", "label": "Vehicles with expiring insurance", "icon": "⚠️"},
]

_RECEIVABLES_OPTIONS: list[dict[str, str]] = [
    {"id": "Show outstanding receivables", "label": "Show outstanding receivables", "icon": "📈"},
    {"id": "Show partner ageing report", "label": "Show partner ageing report", "icon": "🧾"},
    {"id": "Top overdue customers", "label": "Top overdue customers", "icon": "⚠️"},
    {"id": "Receivables summary this month", "label": "Receivables summary this month", "icon": "📊"},
]
_FINANCIAL_REPORT_OPTIONS: list[dict[str, str]] = [
    {"id": "pl", "label": "Profit & Loss Statement", "icon": "📈"},
    {"id": "trial_balance", "label": "Trial Balance", "icon": "⚖️"},
    {"id": "balance_sheet", "label": "Balance Sheet", "icon": "📊"},
    {"id": "cash_flow", "label": "Cash Flow Statement", "icon": "💵"},
    {"id": "general_ledger", "label": "General Ledger", "icon": "📒"},
    {"id": "partner_ageing", "label": "Partner Ageing (AR/AP)", "icon": "🧾"},
]

_REPORT_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btrial\s+balance\b", re.I), "trial_balance"),
    (re.compile(r"\bprofit\b.*\bloss\b|\bp\s*&?\s*l\b", re.I), "pl"),
    (re.compile(r"الربح|الخسارة|أرباح\s*و\s*خسائر", re.UNICODE), "pl"),
    (re.compile(r"\bbalance\s+sheet\b", re.I), "balance_sheet"),
    (re.compile(r"\bcash\s+flow\b", re.I), "cash_flow"),
    (re.compile(r"\bgeneral\s+ledger\b", re.I), "general_ledger"),
    (re.compile(r"\bpartner\s+ageing\b|\bar/ap\b", re.I), "partner_ageing"),
]


def normalize_pick_text(message: str) -> str:
    """Last pill label segment, emoji-stripped, lowercased."""
    text = (message or "").strip()
    if _PICK_SEGMENT_RE.search(text):
        text = _PICK_SEGMENT_RE.split(text)[-1]
    text = _EMOJI_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def detect_financial_report_type(message: str) -> str | None:
    norm = normalize_pick_text(message)
    for pattern, report_type in _REPORT_TYPE_PATTERNS:
        if pattern.search(norm):
            return report_type
    return None


def is_financial_category_pick(message: str) -> bool:
    return bool(_FINANCIAL_CATEGORY_RE.search(normalize_pick_text(message)))


def run_menu_preflight(
    message: str,
    *,
    session_id: str | None,
    language: str = "en",
    skip_clarification: bool = False,
) -> PreflightResult | None:
    """Route pill/menu picks without calling Claude."""
    if not skip_clarification or not session_id:
        return None

    text = (message or "").strip()
    if not text:
        return None

    report_type = detect_financial_report_type(text)
    entities = get_entities(session_id)

    if report_type:
        update_entities(
            session_id,
            intent="financial_reports",
            financial_report_type=report_type,
        )
        from gateway.agent.financial_clarification import run_pl_clarification_preflight

        pl_step = run_pl_clarification_preflight(
            text, session_id=session_id, language=language
        )
        if pl_step:
            return pl_step
        if not has_financial_date_range(session_id, text):
            prompt = (
                "Which period should I use for this financial report?"
                if language != "ar"
                else "أي فترة تريد لهذا التقرير المالي؟"
            )
            return PreflightResult(
                text=prompt,
                ui_blocks=[date_quick_block(prompt)],
                suggestions=[],
            )
        return None

    if entities.get("intent") == "financial_reports" and entities.get("financial_report_type"):
        from gateway.agent.financial_clarification import run_pl_clarification_preflight

        pl_step = run_pl_clarification_preflight(
            text, session_id=session_id, language=language
        )
        if pl_step:
            return pl_step
        if not has_financial_date_range(session_id, text) and not _DATE_IN_QUERY_RE.search(text):
            prompt = (
                "Which period should I use for this financial report?"
                if language != "ar"
                else "أي فترة تريد لهذا التقرير المالي؟"
            )
            return PreflightResult(
                text=prompt,
                ui_blocks=[date_quick_block(prompt)],
                suggestions=[],
            )
        return None

    if is_financial_category_pick(text):
        update_entities(session_id, intent="financial_reports")
        prompt = (
            "Which financial report would you like to view?"
            if language != "ar"
            else "أي تقرير مالي تريد عرضه؟"
        )
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _FINANCIAL_REPORT_OPTIONS)],
            suggestions=[],
        )

    norm = normalize_pick_text(text)

    if _PROJECTS_PICK_RE.match(norm):
        update_entities(session_id, intent="projects")
        prompt = "What would you like to explore in Projects & Costs?" if language != "ar" else "ماذا تريد أن تستكشف في المشاريع والتكاليف؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _PROJECTS_OPTIONS)],
            suggestions=[],
        )

    if _HR_PICK_RE.match(norm):
        update_entities(session_id, intent="hr")
        prompt = "What would you like to look up in HR?" if language != "ar" else "ماذا تريد أن تبحث في الموارد البشرية؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _HR_OPTIONS)],
            suggestions=[],
        )

    if _PAYROLL_PICK_RE.match(norm):
        update_entities(session_id, intent="payroll")
        prompt = "What payroll information do you need?" if language != "ar" else "ما معلومات الرواتب التي تحتاجها؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _PAYROLL_OPTIONS)],
            suggestions=[],
        )

    if _PROCUREMENT_PICK_RE.match(norm):
        update_entities(session_id, intent="procurement")
        prompt = "What would you like to see in Procurement?" if language != "ar" else "ماذا تريد أن تستعرض في المشتريات؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _PROCUREMENT_OPTIONS)],
            suggestions=[],
        )

    if _FLEET_PICK_RE.match(norm):
        update_entities(session_id, intent="fleet")
        prompt = "What fleet information do you need?" if language != "ar" else "ما معلومات الأسطول التي تحتاجها؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _FLEET_OPTIONS)],
            suggestions=[],
        )

    if _RECEIVABLES_PICK_RE.match(norm):
        update_entities(session_id, intent="financial_reports")
        prompt = "What receivables data would you like to see?" if language != "ar" else "ما بيانات المستحقات التي تريد عرضها؟"
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, _RECEIVABLES_OPTIONS)],
            suggestions=[],
        )

    if _SEARCH_PICK_RE.match(norm):
        prompt = "What would you like to search for? Type your query below." if language != "ar" else "عن ماذا تريد البحث؟ اكتب استفسارك أدناه."
        return PreflightResult(
            text=prompt,
            ui_blocks=[],
            suggestions=["Search a project by name", "Find an employee", "Look up a vendor"],
        )

    return None

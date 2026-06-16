"""Deterministic reports wizard steps — avoid Claude on greetings and menu picks."""

from __future__ import annotations

import re
from typing import Any

from gateway.agent.menu_preflight import detect_financial_report_type, normalize_pick_text
from gateway.agent.preflight_blocks import PreflightResult, date_quick_block, pill_block
from gateway.agent.session_entities import get_entities, update_entities

_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|hiya|good\s+(?:morning|afternoon|evening)|salam|"
    r"السلام|مرحبا|أهلا|اهلا)(?:[!.,\s]|$)",
    re.I | re.UNICODE,
)

_REPORT_TYPE_OPTIONS: list[dict[str, str]] = [
    {"id": "pandl", "label": "Profit & Loss", "icon": "📈"},
    {"id": "balance_sheet", "label": "Balance Sheet", "icon": "📊"},
    {"id": "cash_flow", "label": "Cash Flow", "icon": "💵"},
    {"id": "trial_balance", "label": "Trial Balance", "icon": "⚖️"},
    {"id": "project_expense", "label": "Project Expense Summary", "icon": "🏗️"},
]

_REPORT_TYPE_BY_ID = {opt["id"]: opt["label"] for opt in _REPORT_TYPE_OPTIONS}
_REPORT_TYPE_BY_LABEL = {opt["label"].lower(): opt["id"] for opt in _REPORT_TYPE_OPTIONS}


def _detect_reports_template(message: str) -> str | None:
    norm = normalize_pick_text(message)
    if norm in _REPORT_TYPE_BY_LABEL:
        return _REPORT_TYPE_BY_LABEL[norm]
    if norm in _REPORT_TYPE_BY_ID:
        return norm
    financial = detect_financial_report_type(message)
    if financial == "pl":
        return "pandl"
    if financial:
        return financial
    if re.search(r"\bproject\s+expense\b", norm, re.I):
        return "project_expense"
    return None


_ACTION_VERB_RE = re.compile(
    r"\b(generate|create|build|export|download|make)\b",
    re.I,
)


def run_reports_preflight(
    message: str,
    *,
    session_id: str | None,
    language: str = "en",
) -> PreflightResult | None:
    """Return picker UI before calling Claude for reports agent."""
    text = (message or "").strip()
    if not text or not session_id:
        return None

    if _ACTION_VERB_RE.search(text):
        return None

    if _GREETING_RE.match(text):
        intro = (
            "مرحباً! سأساعدك في إنشاء التقارير المالية."
            if language == "ar"
            else "Hello! I can help you generate financial reports."
        )
        prompt = (
            "Which report would you like to generate?"
            if language != "ar"
            else "أي تقرير تريد إنشاءه؟"
        )
        update_entities(session_id, intent="reports")
        return PreflightResult(
            text=intro,
            ui_blocks=[pill_block(prompt, _REPORT_TYPE_OPTIONS, allow_typed_input=False)],
            suggestions=[],
        )

    template = _detect_reports_template(text)
    entities = get_entities(session_id)
    if template:
        update_entities(
            session_id,
            intent="reports",
            financial_report_type=template if template != "project_expense" else None,
            reports_template=template,
        )
        if template == "project_expense":
            prompt = (
                "Enter the project name (or pick a period after):"
                if language != "ar"
                else "أدخل اسم المشروع:"
            )
            return PreflightResult(
                text=prompt,
                ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
                suggestions=[],
            )

        prompt = (
            "Select the report period:"
            if language != "ar"
            else "اختر فترة التقرير:"
        )
        return PreflightResult(
            text=prompt,
            ui_blocks=[date_quick_block(prompt)],
            suggestions=[],
        )

    if entities.get("reports_template") == "project_expense" and not entities.get("project_id"):
        if len(text) >= 3 and not _GREETING_RE.match(text):
            update_entities(session_id, project_name=text)
            prompt = (
                "Select the report period (optional — skip for all-time):"
                if language != "ar"
                else "اختر فترة التقرير (اختياري):"
            )
            return PreflightResult(
                text=prompt,
                ui_blocks=[date_quick_block(prompt)],
                suggestions=[],
            )

    return None

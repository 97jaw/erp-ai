"""Pre-Claude checks for agent chat — date pickers, query correction."""

from __future__ import annotations

import re
from typing import Any

from gateway.agent.menu_preflight import run_menu_preflight
from gateway.agent.preflight_blocks import PreflightResult, date_quick_block, pill_block
from gateway.agent.query_correction import suggest_query_corrections
from gateway.agent.session_entities import (
    get_entities,
    has_procurement_date_range,
    is_procurement_dated_query,
    update_entities_from_message,
)
from gateway.clarify import _DATE_IN_QUERY_RE

_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|hiya|good\s+(?:morning|afternoon|evening)|salam|"
    r"السلام|مرحبا|أهلا|اهلا)(?:[!.,\s]|$)",
    re.I | re.UNICODE,
)

_DATE_ISO_RANGE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    re.I,
)
_FINANCIAL_REPORT_PICK_RE = re.compile(
    r"\b(trial\s+balance|balance\s+sheet|profit\s*&?\s*loss|p\s*&?\s*l|"
    r"general\s+ledger|cash\s+flow|partner\s+ageing)\b",
    re.I,
)


def run_chat_preflight(
    message: str,
    *,
    session_id: str | None,
    language: str = "en",
    skip_clarification: bool = False,
    confirmed_entities: list[Any] | None = None,
    user: Any | None = None,
) -> PreflightResult | None:
    """Return an early response when we should clarify before calling Claude."""
    text = (message or "").strip()
    if not text:
        return None

    if _GREETING_RE.match(text):
        from gateway.agent.welcome_menu import welcome_preflight_result

        return welcome_preflight_result(language=language, user=user)

    if session_id and is_procurement_dated_query(text, session_id):
        if not has_procurement_date_range(session_id, text):
            prompt = (
                "Which period should I use for these LPO / purchase records?"
                if language != "ar"
                else "أي فترة تريد لسجلات أوامر الشراء / LPO؟"
            )
            block = date_quick_block(prompt)
            return PreflightResult(
                text=prompt,
                ui_blocks=[block] if block else [],
                suggestions=[],
            )

    if session_id:
        from gateway.agent.financial_clarification import (
            is_arabic_pl_query,
            run_pl_clarification_preflight,
        )
        from gateway.agent.menu_preflight import detect_financial_report_type
        from gateway.agent.session_entities import (
            has_financial_date_range,
            update_entities,
        )

        report_type = detect_financial_report_type(text)
        if is_arabic_pl_query(text):
            report_type = "pl"
        if report_type:
            update_entities(
                session_id,
                intent="financial_reports",
                financial_report_type=report_type,
            )
            if report_type == "pl":
                pl_step = run_pl_clarification_preflight(
                    text, session_id=session_id, language=language
                )
                if pl_step:
                    return pl_step
            elif not has_financial_date_range(session_id, text) and not _DATE_IN_QUERY_RE.search(text):
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

    menu = run_menu_preflight(
        text,
        session_id=session_id,
        language=language,
        skip_clarification=skip_clarification,
    )
    if menu:
        return menu

    if not skip_clarification and not confirmed_entities:
        correction = suggest_query_corrections(text)
        if correction and correction.get("options"):
            question = str(correction.get("question") or "Did you mean one of these?")
            return PreflightResult(
                text=question,
                ui_blocks=[pill_block(question, correction["options"])],
                suggestions=[],
            )

    return None


def should_auto_default_financial_dates(message: str) -> bool:
    """Trial balance / P&L menu picks without an explicit period."""
    if _DATE_IN_QUERY_RE.search(message or ""):
        return False
    if _DATE_ISO_RANGE_RE.search(message or ""):
        return False
    return bool(_FINANCIAL_REPORT_PICK_RE.search(message or ""))

"""Clear stale session intent when the user shifts topic mid-conversation."""

from __future__ import annotations

import re

from gateway.agent.session_entities import get_entities, update_entities

# Clear financial context when the message is clearly about another domain.
_NON_FINANCIAL_TOPIC_RE = re.compile(
    r"\b(?:employee|employees|staff|workers?|headcount|head\s*count)\b|"
    r"\bhow\s+many\s+departments?\b|"
    r"\b(?:department|departments|dept)\s+(?:list|count|structure)\b|"
    r"\b(?:attendance|leave|payroll|payslip|salary|wages?)\b|"
    r"\b(?:vehicle|vehicles|fleet|license\s*plate)\b|"
    r"\b(?:purchase\s+order|purchase\s+orders|lpo|rfq|procurement)\b|"
    r"\b(?:project\s+cost|project\s+expense|active\s+projects?)\b|"
    r"\bwho\s+owes\b|"
    r"\b(?:موظف|موظفين|قسم|أقسام|حضور|رواتب|مركبات)\b",
    re.I | re.UNICODE,
)


def message_continues_financial_flow(message: str) -> bool:
    """True when this turn is part of an in-progress financial report flow."""
    text = (message or "").strip()
    if not text:
        return False

    from gateway.agent.financial_clarification import (
        detect_scope_pick,
        detect_target_move_pick,
        is_arabic_pl_query,
    )
    from gateway.agent.menu_preflight import (
        detect_financial_report_type,
        is_financial_category_pick,
    )
    from gateway.agent.session_entities import extract_date_range_from_text
    from gateway.clarify import _DATE_IN_QUERY_RE

    if (
        detect_financial_report_type(text)
        or is_financial_category_pick(text)
        or is_arabic_pl_query(text)
        or detect_scope_pick(text)
        or detect_target_move_pick(text)
        or extract_date_range_from_text(text)
        or _DATE_IN_QUERY_RE.search(text)
    ):
        return True

    lowered = text.lower()
    financial_tokens = (
        "trial balance",
        "general ledger",
        "balance sheet",
        "cash flow",
        "profit",
        "loss",
        "partner ageing",
        "financial report",
        "p&l",
        "p & l",
        "الربح",
        "الخسارة",
        "ميزان",
    )
    return any(token in lowered for token in financial_tokens)


def is_non_financial_topic(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if message_continues_financial_flow(text):
        return False
    return bool(_NON_FINANCIAL_TOPIC_RE.search(text))


def reconcile_session_intent(session_id: str, message: str) -> None:
    """Drop stale financial intent when the user clearly changed topic."""
    if not session_id:
        return

    entities = get_entities(session_id)
    text = (message or "").strip()
    if not text or entities.get("intent") != "financial_reports":
        return

    if is_non_financial_topic(text):
        from gateway.agent.session_entities import clear_financial_entities

        clear_financial_entities(session_id)
        if re.search(r"\b(?:employee|employees|staff)\b", text, re.I):
            update_entities(session_id, intent="hr")
        return

    if not message_continues_financial_flow(text):
        from gateway.agent.session_entities import clear_financial_entities

        clear_financial_entities(session_id)

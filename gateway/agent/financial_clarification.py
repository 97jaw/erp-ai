"""Multi-step clarification for P&L before fetching data."""

from __future__ import annotations

import re
from typing import Any

from gateway.agent.preflight_blocks import PreflightResult, date_quick_block, pill_block
from gateway.agent.session_entities import (
    extract_date_range_from_text,
    get_entities,
    has_financial_date_range,
    update_entities,
)
from gateway.clarify import _DATE_IN_QUERY_RE

_AR_PL_RE = re.compile(r"الربح|الخسارة|أرباح|خسائر", re.UNICODE)

_SCOPE_OPTIONS: list[dict[str, str]] = [
    {"id": "company", "label": "Company-wide (all projects)", "icon": "🏢"},
    {"id": "project", "label": "Specific project", "icon": "🏗️"},
]

_SCOPE_OPTIONS_AR: list[dict[str, str]] = [
    {"id": "company", "label": "على مستوى الشركة (كل المشاريع)", "icon": "🏢"},
    {"id": "project", "label": "مشروع محدد", "icon": "🏗️"},
]

_TARGET_MOVE_OPTIONS: list[dict[str, str]] = [
    {"id": "posted", "label": "Posted entries only", "icon": "✅"},
    {"id": "all", "label": "All entries (incl. drafts)", "icon": "📂"},
]

_TARGET_MOVE_OPTIONS_AR: list[dict[str, str]] = [
    {"id": "posted", "label": "القيود المرحّلة فقط", "icon": "✅"},
    {"id": "all", "label": "جميع القيود (بما فيها المسودات)", "icon": "📂"},
]

_PL_CLARIFY_TYPES = frozenset({"pl"})


def is_arabic_pl_query(message: str) -> bool:
    return bool(_AR_PL_RE.search(message or ""))


def detect_scope_pick(message: str) -> str | None:
    norm = (message or "").strip().lower()
    if norm in {"company", "company-wide", "overall", "whole company"}:
        return "company"
    if norm in {"project", "specific project", "project-specific"}:
        return "project"
    if "company-wide" in norm or "all projects" in norm or "overall" in norm:
        return "company"
    if "specific project" in norm or norm.startswith("project"):
        return "project"
    if "على مستوى الشركة" in message or "كل المشاريع" in message:
        return "company"
    if "مشروع محدد" in message:
        return "project"
    return None


def detect_target_move_pick(message: str) -> str | None:
    norm = (message or "").strip().lower()
    if norm in {"posted", "posted entries only", "posted only"}:
        return "posted"
    if norm in {"all", "all entries", "all entries (incl. drafts)"}:
        return "all"
    if "posted" in norm and "all" not in norm:
        return "posted"
    if "draft" in norm or "all entries" in norm:
        return "all"
    if "المرحّلة" in message or "مرحلة" in message:
        return "posted"
    if "مسودات" in message or "جميع القيود" in message:
        return "all"
    return None


def pl_clarification_complete(session_id: str) -> bool:
    entities = get_entities(session_id)
    if entities.get("financial_report_type") not in _PL_CLARIFY_TYPES:
        return True
    if not entities.get("financial_scope"):
        return False
    if not entities.get("financial_target_move"):
        return False
    if entities.get("financial_scope") == "project":
        if not entities.get("project_id") and not entities.get("project_name"):
            return False
    return True


def run_pl_clarification_preflight(
    message: str,
    *,
    session_id: str,
    language: str = "en",
) -> PreflightResult | None:
    """Ask date → scope → entry type for P&L (English and Arabic)."""
    entities = get_entities(session_id)
    report_type = entities.get("financial_report_type")
    if report_type not in _PL_CLARIFY_TYPES:
        return None

    scope_pick = detect_scope_pick(message)
    if scope_pick:
        update_entities(session_id, financial_scope=scope_pick)
    target_pick = detect_target_move_pick(message)
    if target_pick:
        update_entities(session_id, financial_target_move=target_pick)

    entities = get_entities(session_id)
    if (
        entities.get("financial_scope") == "project"
        and not entities.get("project_id")
        and not entities.get("project_name")
        and message.strip()
        and not scope_pick
        and not target_pick
        and not _DATE_IN_QUERY_RE.search(message)
        and not extract_date_range_from_text(message)
    ):
        update_entities(session_id, project_name=message.strip())
        entities = get_entities(session_id)

    entities = get_entities(session_id)

    if not has_financial_date_range(session_id, message) and not _DATE_IN_QUERY_RE.search(message):
        prompt = (
            "Which period should I use for the Profit & Loss report?"
            if language != "ar"
            else "أي فترة تريد لتقرير الأرباح والخسائر؟"
        )
        return PreflightResult(text=prompt, ui_blocks=[date_quick_block(prompt)], suggestions=[])

    if not entities.get("financial_scope"):
        prompt = (
            "Should this P&L cover the whole company or a specific project?"
            if language != "ar"
            else "هل تريد الأرباح والخسائر على مستوى الشركة أم لمشروع محدد؟"
        )
        options = _SCOPE_OPTIONS if language != "ar" else _SCOPE_OPTIONS_AR
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, options)],
            suggestions=[],
        )

    if entities.get("financial_scope") == "project" and not entities.get("project_id"):
        if not entities.get("project_name"):
            prompt = (
                "Which project should I use? Type the project name or WO reference."
                if language != "ar"
                else "أي مشروع تريد؟ اكتب اسم المشروع أو رقم أمر العمل."
            )
            return PreflightResult(
                text=prompt,
                ui_blocks=[
                    pill_block(prompt, [], allow_typed_input=True),
                ],
                suggestions=[],
            )

    if not entities.get("financial_target_move"):
        prompt = (
            "Which journal entries should I include?"
            if language != "ar"
            else "أي قيود تريد تضمينها؟"
        )
        options = _TARGET_MOVE_OPTIONS if language != "ar" else _TARGET_MOVE_OPTIONS_AR
        return PreflightResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, options)],
            suggestions=[],
        )

    return None

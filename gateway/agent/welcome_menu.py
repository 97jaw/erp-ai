"""Top-level welcome menu — shared options for greeting preflight and UI seed."""

from __future__ import annotations

from typing import Any

from gateway.agent.preflight_blocks import PreflightResult, pill_block

TOP_MENU_OPTIONS: list[dict[str, str]] = [
    {"id": "financial", "label": "Financial Reports", "icon": "📊"},
    {"id": "projects", "label": "Projects & Costs", "icon": "🏗️"},
    {"id": "documents", "label": "Documents & Files", "icon": "📎"},
    {"id": "hr", "label": "HR & Employees", "icon": "👥"},
    {"id": "payroll", "label": "Payroll & Payslips", "icon": "💰"},
    {"id": "procurement", "label": "Procurement & LPOs", "icon": "📋"},
    {"id": "fleet", "label": "Fleet & Vehicles", "icon": "🚗"},
    {"id": "receivables", "label": "Receivables & AR", "icon": "📈"},
    {"id": "search", "label": "Search / Ask Anything", "icon": "🔍"},
]


def welcome_intro_text(*, language: str = "en", user_name: str | None = None) -> str:
    name = (user_name or "").strip()
    if language == "ar":
        if name:
            return f"مرحباً {name}! أنا مساعدك الذكي لنظام Elrace ERP. ماذا تريد أن تستكشف؟"
        return "مرحباً! أنا مساعدك الذكي لنظام Elrace ERP. ماذا تريد أن تستكشف؟"
    if name:
        return f"Hello {name}! I'm your Elrace ERP assistant. What would you like to explore?"
    return "Hello! I'm your Elrace ERP assistant. What would you like to explore?"


def welcome_preflight_result(
    *,
    language: str = "en",
    user: Any | None = None,
) -> PreflightResult:
    user_name = getattr(user, "name", None) if user else None
    intro = welcome_intro_text(language=language, user_name=user_name)
    prompt = (
        "What would you like to explore?"
        if language != "ar"
        else "ماذا تريد أن تستكشف؟"
    )
    return PreflightResult(
        text=intro,
        ui_blocks=[pill_block(prompt, TOP_MENU_OPTIONS)],
        suggestions=[
            "Show trial balance",
            "How many departments do we have?",
            "Show active projects",
        ],
    )

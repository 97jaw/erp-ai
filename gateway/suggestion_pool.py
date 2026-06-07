"""Post-response suggestion pools and session rotation (Phase 6)."""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

CACHE_TTL_SECONDS = 7200


class SuggestionContext(str, Enum):
    PANDL = "pandl"
    BALANCE_SHEET = "balance_sheet"
    TRIAL_BALANCE = "trial_balance"
    GENERAL_LEDGER = "general_ledger"
    PARTNER_AGEING = "partner_ageing"
    PROJECT = "project"
    RECEIVABLES = "receivables"
    COMPARISON = "comparison"
    DATA_TABLE = "data_table"
    BAR_CHART = "bar_chart"
    GENERAL = "general"


PANDL_SUGGESTIONS: dict[str, list[str]] = {
    "drill_down": [
        "Break down expenses by account",
        "Show top 5 cost categories",
        "Show income breakdown by client",
        "Which projects contributed most to revenue?",
    ],
    "comparison": [
        "Compare with last month",
        "Compare with same period last year",
        "Show P&L trend for last 6 months",
    ],
    "filter": [
        "Show only direct project costs",
        "Exclude administrative expenses",
        "Group by operating unit",
    ],
    "export": [
        "Generate executive PDF report",
        "Export to Excel for analysis",
    ],
    "analysis": [
        "Why is the margin lower than last month?",
        "Which expense categories can be reduced?",
        "Identify any unusual transactions",
    ],
}

BALANCE_SHEET_SUGGESTIONS: dict[str, list[str]] = {
    "analysis": [
        "What is our current ratio?",
        "How has working capital changed?",
        "Compare assets vs liabilities trend",
    ],
    "detail": [
        "Show breakdown of current assets",
        "List all outstanding receivables",
        "Show fixed assets by category",
    ],
}

PROJECT_SUGGESTIONS: dict[str, list[str]] = {
    "costs": [
        "Break down costs by LPO, petty cash, labor",
        "Show cost trend over project timeline",
        "Compare planned vs actual costs",
    ],
    "comparison": [
        "Compare all active projects side by side",
        "Which projects are over budget?",
        "Show top 5 most profitable projects",
    ],
    "client": [
        "Show all projects for this client",
        "What is total revenue from this client?",
    ],
}

RECEIVABLES_SUGGESTIONS: dict[str, list[str]] = {
    "priority": [
        "Which client is most overdue?",
        "Show invoices overdue by more than 60 days",
        "Show collection priority list",
    ],
    "client": [
        "Show full ledger for this client",
        "View payment history by client",
    ],
}

AR_SUGGESTIONS: dict[str, str] = {
    "Compare with last month": "قارن مع الشهر الماضي",
    "Show top 5 cost categories": "اعرض أهم 5 فئات تكلفة",
    "Break down expenses by account": "فصّل المصروفات حسب الحساب",
    "Generate executive PDF report": "أنشئ تقرير PDF تنفيذي",
    "Which projects are over budget?": "ما المشاريع التي تجاوزت الميزانية؟",
    "Show profit and loss this month": "اعرض الأرباح والخسائر لهذا الشهر",
}


@dataclass
class SuggestionSessionState:
    pool: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)
    context: SuggestionContext = SuggestionContext.GENERAL
    language: str = "en"
    expires_at: float = 0.0


class SuggestionSessionStore:
    _by_token: dict[str, SuggestionSessionState] = {}

    @classmethod
    def _purge(cls) -> None:
        now = time.monotonic()
        expired = [token for token, state in cls._by_token.items() if now >= state.expires_at]
        for token in expired:
            cls._by_token.pop(token, None)

    @classmethod
    def register(cls, pool: list[str], context: SuggestionContext, language: str) -> str:
        cls._purge()
        token = uuid.uuid4().hex[:16]
        cls._by_token[token] = SuggestionSessionState(
            pool=list(pool),
            shown=[],
            context=context,
            language=language,
            expires_at=time.monotonic() + CACHE_TTL_SECONDS,
        )
        return token

    @classmethod
    def get(cls, token: str) -> SuggestionSessionState | None:
        cls._purge()
        state = cls._by_token.get(token)
        if not state or time.monotonic() >= state.expires_at:
            cls._by_token.pop(token, None)
            return None
        return state


def _translate_suggestion(text: str, language: str) -> str:
    if language != "ar":
        return text
    return AR_SUGGESTIONS.get(text, text)


def detect_suggestion_context(
    tool_names: list[str],
    visualization: dict[str, Any] | None,
) -> SuggestionContext:
    visual_type = (visualization or {}).get("visual_type") or ""
    if visual_type == "FINANCIAL_REPORT":
        label = str((visualization or {}).get("label") or "").lower()
        if "balance" in label:
            return SuggestionContext.BALANCE_SHEET
        return SuggestionContext.PANDL
    if visual_type == "BAR_CHART":
        return SuggestionContext.BAR_CHART
    if visual_type == "DATA_TABLE":
        return SuggestionContext.DATA_TABLE

    for tool_name in reversed(tool_names or []):
        if tool_name == "get_financial_report":
            return SuggestionContext.PANDL
        if tool_name == "get_balance_sheet":
            return SuggestionContext.BALANCE_SHEET
        if tool_name == "get_trial_balance":
            return SuggestionContext.TRIAL_BALANCE
        if tool_name == "get_general_ledger":
            return SuggestionContext.GENERAL_LEDGER
        if tool_name == "get_partner_ageing":
            return SuggestionContext.RECEIVABLES
        if tool_name in {
            "get_project_expenses",
            "get_project_financial_data",
            "get_project_cost_categories",
            "get_top_projects_by_metric",
            "get_projects_with_overrun",
        }:
            return SuggestionContext.PROJECT
        if tool_name == "get_period_comparison":
            return SuggestionContext.COMPARISON

    return SuggestionContext.GENERAL


def extract_data_context(
    visualization: dict[str, Any] | None,
    tool_results: list[Any] | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if visualization:
        kpis = visualization.get("kpis") or {}
        if isinstance(kpis, dict):
            context.update(kpis)
        context["visual_type"] = visualization.get("visual_type")
        context["label"] = visualization.get("label")

    for result in reversed(tool_results or []):
        if not isinstance(result, dict):
            continue
        if result.get("kpis"):
            context.update({k: v for k, v in result["kpis"].items() if isinstance(v, (int, float))})
        if result.get("projects") and isinstance(result["projects"], list):
            context["project_count"] = len(result["projects"])
        if result.get("over_budget") or result.get("status") == "over_budget":
            context["over_budget"] = True
        break

    return context


def get_suggestion_pool(context: SuggestionContext, data: dict[str, Any]) -> list[str]:
    pool: list[str] = []

    if context == SuggestionContext.PANDL:
        for items in PANDL_SUGGESTIONS.values():
            pool.extend(items)
        if float(data.get("net_profit", 0) or 0) < 0:
            pool.insert(0, "Why is this period showing a loss?")
        if float(data.get("margin", 100) or 100) < 15:
            pool.insert(0, "How can we improve the profit margin?")
    elif context == SuggestionContext.BALANCE_SHEET:
        for items in BALANCE_SHEET_SUGGESTIONS.values():
            pool.extend(items)
    elif context == SuggestionContext.PROJECT:
        for items in PROJECT_SUGGESTIONS.values():
            pool.extend(items)
        if data.get("over_budget"):
            pool.insert(0, "Show which cost category caused the overrun")
    elif context == SuggestionContext.RECEIVABLES:
        for items in RECEIVABLES_SUGGESTIONS.values():
            pool.extend(items)
    elif context == SuggestionContext.COMPARISON:
        pool.extend([
            "Show profit and loss this month",
            "Drill into the biggest change driver",
            "Export comparison to PDF",
        ])
    elif context == SuggestionContext.GENERAL_LEDGER:
        pool.extend([
            "Show trial balance",
            "Filter by specific account",
            "Show profit and loss for this period",
        ])
    elif context == SuggestionContext.TRIAL_BALANCE:
        pool.extend([
            "Show general ledger for largest account",
            "Show profit and loss",
            "Compare with last month",
        ])
    elif context == SuggestionContext.BAR_CHART:
        pool.extend([
            "Drill into the top category",
            "Compare with the previous period",
            "Show underlying transactions",
        ])
    elif context == SuggestionContext.DATA_TABLE:
        pool.extend([
            "Export this table to Excel",
            "Filter to the top 10 rows only",
            "Compare with the previous period",
        ])
    else:
        pool.extend([
            "Show more details",
            "Compare with last month",
            "Generate a PDF report",
        ])

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in pool:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())
    return unique


def pick_diverse_suggestions(
    pool: list[str],
    count: int = 3,
    *,
    exclude: set[str] | None = None,
) -> list[str]:
    exclude = exclude or set()
    available = [item for item in pool if item not in exclude]
    if len(available) <= count:
        return available[:count]

    categories: dict[str, list[str]] = {
        "drill": [],
        "compare": [],
        "filter": [],
        "export": [],
        "analysis": [],
    }
    for suggestion in available:
        lower = suggestion.lower()
        if any(word in lower for word in ("compare", "vs", "trend", "last month", "last year")):
            categories["compare"].append(suggestion)
        elif any(word in lower for word in ("filter", "only", "exclude", "group")):
            categories["filter"].append(suggestion)
        elif any(word in lower for word in ("pdf", "excel", "export", "generate")):
            categories["export"].append(suggestion)
        elif any(word in lower for word in ("break", "show", "list", "drill", "top")):
            categories["drill"].append(suggestion)
        else:
            categories["analysis"].append(suggestion)

    selected: list[str] = []
    for category in ("drill", "compare", "analysis", "filter", "export"):
        if len(selected) >= count:
            break
        options = [item for item in categories[category] if item not in selected]
        if options:
            selected.append(random.choice(options))

    if len(selected) < count:
        for item in available:
            if item not in selected:
                selected.append(item)
            if len(selected) >= count:
                break

    return selected[:count]


def build_post_response_suggestions(
    *,
    model_suggestions: list[str] | None,
    tool_names: list[str],
    tool_results: list[Any] | None,
    visualization: dict[str, Any] | None,
    language: str = "en",
    session_id: str | None = None,
) -> tuple[list[str], dict[str, Any] | None]:
    if not tool_names and not visualization:
        return (model_suggestions or [])[:3], None

    context = detect_suggestion_context(tool_names, visualization)
    data_context = extract_data_context(visualization, tool_results)
    pool = get_suggestion_pool(context, data_context)

    preferred = [str(item).strip() for item in (model_suggestions or []) if str(item).strip()]
    token = SuggestionSessionStore.register(pool, context, language) if session_id else None

    selected: list[str] = []
    seen: set[str] = set()
    for item in preferred:
        if item not in seen and len(item) <= 90:
            seen.add(item)
            selected.append(_translate_suggestion(item, language))
        if len(selected) >= 3:
            break

    if len(selected) < 3:
        filler = pick_diverse_suggestions(
            [_translate_suggestion(item, language) for item in pool],
            3 - len(selected),
            exclude=set(selected),
        )
        selected.extend(filler)

    selected = selected[:3]

    if token:
        state = SuggestionSessionStore.get(token)
        if state:
            state.shown.extend(selected)

    has_more = bool(token and len(pool) > len(selected))
    meta = {
        "token": token,
        "has_more": has_more,
        "context": context.value,
    } if token else None

    return selected, meta


def rotate_post_response_suggestions(token: str, *, count: int = 3) -> tuple[list[str], bool]:
    state = SuggestionSessionStore.get(token)
    if not state:
        return [], False

    shown_set = set(state.shown)
    translated_pool = [_translate_suggestion(item, state.language) for item in state.pool]
    fresh = [item for item in translated_pool if item not in shown_set]

    if len(fresh) < count:
        state.shown = list(selected for selected in state.shown[-3:] if selected)
        shown_set = set(state.shown)
        fresh = [item for item in translated_pool if item not in shown_set]

    next_batch = pick_diverse_suggestions(fresh, count, exclude=shown_set)
    state.shown.extend(next_batch)
    has_more = len(set(state.shown)) < len(translated_pool)
    return next_batch, has_more

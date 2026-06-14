"""Context-aware suggestion generation — whitelist-only (Phase 7 refactor).

Every suggestion must correspond to a real, working capability.
If the context is unclear, we return nothing rather than guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent
from gateway.core.proactive_intelligence import PredictedAction, _top_client_from_visualization
from gateway.core.result_synthesizer import SynthesizedResult
from gateway.suggestion_pool import (
    SuggestionContext,
    detect_suggestion_context,
    extract_data_context,
    pick_diverse_suggestions,
)

MAX_SUGGESTION_LENGTH = 90
TARGET_COUNT = 3

# ---------------------------------------------------------------------------
# Whitelist pools — ONLY suggestions that map to real tools/capabilities
# ---------------------------------------------------------------------------

_EXPENSE_POOL = [
    "Show breakdown of {project} expenses",
    "Compare {project} with another project",
    "Show last 3 months expenses for {project}",
    "Show top 5 projects by expense this year",
    "Most expensive project by labor cost",
]

_PROJECT_LIST_POOL = [
    "Group by client",
    "Show top 5 by expense",
    "Filter active projects only",
    "Client wise projects of {year}",
]

_PAYROLL_POOL = [
    "Show payroll breakdown by department",
    "Total payroll cost last month",
    "Draft payslips count",
    "Average labor cost per project",
]

_HR_POOL = [
    "Show employees by department",
    "How many employees do we have",
    "Employees in Civil department",
]

_FINANCIAL_POOL = [
    "Show trial balance",
    "Show P&L for this year",
    "Partner ageing report",
    "Revenue by client last quarter",
]

_AUDIT_POOL = [
    "Show changes last week on {project}",
    "Who modified {project} this week",
    "Recent stage changes on projects",
]

_RECORDS_SIBLINGS = {
    "invoices":          "Show {p} purchase orders",
    "client_invoices":   "Show {p} LPO invoices",
    "lpo_invoices":      "Show {p} client invoices",
    "purchase_orders":   "Show {p} LPO invoices",
    "timesheets":        "Show {p} staff list",
    "petty_cash":        "Show {p} petty cash sheets",
    "petty_cash_sheets": "Show {p} petty cash expenses",
    "staff":             "Show {p} supervisors",
    "supervisors":       "Show {p} staff list",
}


@dataclass(frozen=True)
class Suggestion:
    """One ranked follow-up suggestion."""

    text: str
    category: str
    priority: int = 0


class SmartSuggestionsGenerator:
    """Build diverse, whitelist-only suggestions from the current response."""

    def generate(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
        *,
        tool_names: list[str],
        tool_results: list[Any],
        language: str = "en",
        predicted_actions: list[PredictedAction] | None = None,
    ) -> list[str]:
        """Return up to three diverse, actionable suggestion strings."""
        candidates = self._build_candidates(
            synthesized, intent, context,
            tool_names=tool_names, tool_results=tool_results,
        )
        eligible = self._filter_eligible(candidates, context)
        diverse = self._diversify(eligible, target_count=TARGET_COUNT)
        return [item.text[:MAX_SUGGESTION_LENGTH] for item in diverse]

    def _build_candidates(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
        *,
        tool_names: list[str],
        tool_results: list[Any],
    ) -> list[Suggestion]:
        # --- Tool-specific whitelists (highest priority) ---
        if "get_project_profile" in tool_names:
            return self._project_profile_suggestions(context, tool_results)
        if "get_project_records" in tool_names:
            return self._project_records_suggestions(context, tool_results)
        if "get_project_activity" in tool_names:
            return self._project_activity_suggestions(context, tool_results)

        # --- Expense tools ---
        if any(n in tool_names for n in (
            "get_project_expenses", "get_project_expense_summary",
            "get_project_expense_breakdown", "get_project_financial_data",
            "get_project_cost_categories", "compare_project_expenses",
        )):
            return self._expense_suggestions(context, tool_results, synthesized)

        # --- List query results ---
        if any(n in tool_names for n in ("execute_query_odoo", "execute_aggregate_odoo")):
            return self._list_suggestions(intent, context, tool_results)

        # --- Financial reports ---
        suggestion_context = detect_suggestion_context(tool_names, synthesized.visualization, tool_results)
        if suggestion_context in {
            SuggestionContext.PANDL, SuggestionContext.TRIAL_BALANCE,
            SuggestionContext.GENERAL_LEDGER, SuggestionContext.BALANCE_SHEET,
            SuggestionContext.RECEIVABLES, SuggestionContext.PARTNER_AGEING,
        }:
            return self._financial_suggestions(suggestion_context, synthesized, tool_results)

        # --- HR / Payroll ---
        from gateway.core.payroll_query_routing import is_payroll_orchestration_query
        pending = context.working_memory.session_facts.get("pending_entity_clarification") or {}
        payroll_turn = (
            intent.subject_area in {"payroll", "hr"}
            or is_payroll_orchestration_query(
                context.conversation.message or intent.specific_intent, intent, context,
            )
            or bool(pending.get("payroll_context"))
        )
        if suggestion_context == SuggestionContext.PAYROLL or (intent.subject_area == "payroll" and payroll_turn):
            pool = list(_PAYROLL_POOL)
            if pending.get("payroll_context"):
                pool = ["Show payslip for last month", "Total payroll cost last month", *pool]
            return [Suggestion(text=t, category="drill", priority=5) for t in pool[:TARGET_COUNT]]

        if suggestion_context == SuggestionContext.HR or intent.subject_area == "hr":
            return [Suggestion(text=t, category="drill", priority=5) for t in _HR_POOL[:TARGET_COUNT]]

        # --- Audit ---
        if any(n in tool_names for n in ("audit_query", "audit_search")):
            return self._audit_suggestions(context)

        # Unknown context — return nothing (empty is better than wrong)
        return []

    @staticmethod
    def _project_profile_suggestions(context: ContextStack, tool_results: list[Any]) -> list[Suggestion]:
        project_name = None
        focus = "all"
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("_source") == "project_profile":
                project_name = payload.get("project_name")
                focus = str(payload.get("focus") or "all")
                break
        if not project_name:
            active = context.working_memory.get_active_project()
            project_name = active.project_name if active is not None else None
        if not project_name:
            return []

        out = []
        if focus not in {"schedule", "all"}:
            out.append(Suggestion(f"Show {project_name} schedule and duration", "drill", 5))
        if focus != "team":
            out.append(Suggestion(f"Who is the project manager of {project_name}?", "drill", 4))
        out.append(Suggestion(f"Show {project_name} expenses", "action", 3))
        return [s for s in out if len(s.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _project_records_suggestions(context: ContextStack, tool_results: list[Any]) -> list[Suggestion]:
        project_name = None
        record_type = ""
        period_defaulted = False
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("_source") == "project_records":
                project_name = payload.get("project_name")
                record_type = str(payload.get("record_type") or "")
                period_defaulted = bool((payload.get("period") or {}).get("defaulted"))
                break
        if not project_name:
            active = context.working_memory.get_active_project()
            project_name = active.project_name if active is not None else "the project"

        out = []
        sibling = _RECORDS_SIBLINGS.get(record_type)
        if sibling:
            out.append(Suggestion(sibling.format(p=project_name), "drill", 5))
        if period_defaulted:
            out.append(Suggestion(
                f"Show {project_name} {record_type.replace('_', ' ')} for this year",
                "time", 4,
            ))
        out.append(Suggestion(f"Show {project_name} expenses", "action", 3))
        return [s for s in out if len(s.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _project_activity_suggestions(context: ContextStack, tool_results: list[Any]) -> list[Suggestion]:
        project_name = None
        activity_type = ""
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("_source") == "project_activity":
                project_name = payload.get("project_name")
                activity_type = str(payload.get("activity_type") or "")
                break
        if not project_name:
            active = context.working_memory.get_active_project()
            project_name = active.project_name if active is not None else None
        if not project_name:
            return []

        # Only suggest real activity_type values (attachments/chatter_summary/progress/audit)
        siblings: dict[str, list[tuple[str, str]]] = {
            "attachments":    [(f"Chatter summary of {project_name}", "drill"),
                               (f"Show {project_name} progress", "drill")],
            "chatter_summary":[(f"Attachments of {project_name}", "drill"),
                               (f"Last updated by for {project_name}", "drill")],
            "progress":       [(f"Attachments of {project_name}", "drill"),
                               (f"Show {project_name} schedule and duration", "drill")],
            "audit":          [(f"Chatter summary of {project_name}", "drill"),
                               (f"Show {project_name} progress", "drill")],
        }
        return [
            Suggestion(text, cat, 5)
            for text, cat in siblings.get(activity_type, [])
            if len(text) <= MAX_SUGGESTION_LENGTH
        ][:TARGET_COUNT]

    @staticmethod
    def _expense_suggestions(
        context: ContextStack, tool_results: list[Any], synthesized: SynthesizedResult,
    ) -> list[Suggestion]:
        active = context.working_memory.get_active_project()
        project_name = active.project_name if active is not None else None
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("project_name"):
                project_name = payload["project_name"]
                break

        out = []
        if project_name:
            out.append(Suggestion(f"Show breakdown of {project_name} expenses", "drill", 5))
            out.append(Suggestion(f"Compare {project_name} with another project", "compare", 4))
        out.append(Suggestion("Show top 5 projects by expense this year", "drill", 3))

        # Data-specific: if in loss, offer why-analysis
        data = extract_data_context(synthesized.visualization, tool_results)
        if float(data.get("net_profit", 0) or 0) < 0:
            out.insert(0, Suggestion("Why is this period showing a loss?", "analysis", 6))
        if data.get("over_budget"):
            out.insert(0, Suggestion("Show which cost category caused the overrun", "analysis", 6))

        return [s for s in out if len(s.text) <= MAX_SUGGESTION_LENGTH][:TARGET_COUNT + 1]

    @staticmethod
    def _list_suggestions(
        intent: Intent, context: ContextStack, tool_results: list[Any],
    ) -> list[Suggestion]:
        """After a list/aggregate query — offer grouped/filtered variants."""
        subject = (intent.subject_area or "").lower()
        out = []
        if subject in {"project", ""}:
            out.append(Suggestion("Client wise projects of 2025", "drill", 5))
            out.append(Suggestion("Show top 5 projects by expense this year", "drill", 4))
            out.append(Suggestion("Active projects of 2026", "filter", 3))
        elif subject == "financial":
            out.extend(Suggestion(t, "drill", 4) for t in _FINANCIAL_POOL[:3])
        elif subject in {"payroll", "hr"}:
            out.extend(Suggestion(t, "drill", 4) for t in _PAYROLL_POOL[:3])
        # Generic: return nothing rather than wrong suggestions
        return [s for s in out if len(s.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _financial_suggestions(
        suggestion_context: SuggestionContext,
        synthesized: SynthesizedResult,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        # Whitelist per report type — only real tools
        pools: dict[SuggestionContext, list[str]] = {
            SuggestionContext.PANDL: [
                "Break down expenses by account",
                "Show top 5 cost categories",
                "Compare with last month",
            ],
            SuggestionContext.TRIAL_BALANCE: [
                "Show general ledger for this period",
                "Show P&L for this year",
                "Compare with last month",
            ],
            SuggestionContext.GENERAL_LEDGER: [
                "Show trial balance",
                "Show P&L for this period",
                "Filter by specific account",
            ],
            SuggestionContext.BALANCE_SHEET: [
                "Show breakdown of current assets",
                "List all outstanding receivables",
                "Compare assets vs liabilities trend",
            ],
            SuggestionContext.RECEIVABLES: [
                "Which client is most overdue?",
                "Show invoices overdue by more than 60 days",
                "Show collection priority list",
            ],
            SuggestionContext.PARTNER_AGEING: [
                "Which client is most overdue?",
                "Show invoices overdue by more than 60 days",
            ],
        }
        data = extract_data_context(synthesized.visualization, tool_results)
        chosen = pools.get(suggestion_context, [])
        out = [Suggestion(t, "drill", 5) for t in chosen]
        if float(data.get("net_profit", 0) or 0) < 0:
            out.insert(0, Suggestion("Why is this period showing a loss?", "analysis", 6))
        return out[:TARGET_COUNT]

    @staticmethod
    def _audit_suggestions(context: ContextStack) -> list[Suggestion]:
        active = context.working_memory.get_active_project()
        project_name = active.project_name if active is not None else None
        if project_name:
            return [
                Suggestion(f"Show changes last week on {project_name}", "drill", 5),
                Suggestion(f"Who modified {project_name} this week", "drill", 4),
                Suggestion("Recent stage changes on projects", "drill", 3),
            ]
        return [
            Suggestion("Show changes last week", "drill", 5),
            Suggestion("Recent stage changes on projects", "drill", 4),
        ]

    @staticmethod
    def _filter_eligible(candidates: list[Suggestion], context: ContextStack) -> list[Suggestion]:
        shown = {
            str(item).strip().lower()
            for item in context.working_memory.session_facts.get("shown_suggestions") or []
        }
        eligible: list[Suggestion] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = candidate.text.strip()
            if not text or len(text) > MAX_SUGGESTION_LENGTH:
                continue
            key = text.lower()
            if key in seen or key in shown:
                continue
            if _is_permission_blocked(text, context):
                continue
            seen.add(key)
            eligible.append(candidate)
        return eligible

    @staticmethod
    def _diversify(candidates: list[Suggestion], *, target_count: int) -> list[Suggestion]:
        if not candidates:
            return []
        ordered = sorted(candidates, key=lambda item: item.priority, reverse=True)
        selected: list[Suggestion] = []
        seen_cats: dict[str, int] = {}
        for candidate in ordered:
            if len(selected) >= target_count:
                break
            if candidate.text in {s.text for s in selected}:
                continue
            # Allow max 2 from same category for diversity
            cat_count = seen_cats.get(candidate.category, 0)
            if cat_count >= 2 and len(selected) < target_count - 1:
                continue
            selected.append(candidate)
            seen_cats[candidate.category] = cat_count + 1
        # Fill remaining slots if diversity filter left gaps
        for candidate in ordered:
            if len(selected) >= target_count:
                break
            if candidate.text not in {s.text for s in selected}:
                selected.append(candidate)
        return selected[:target_count]


def remember_shown_suggestions(context: ContextStack, suggestions: list[str]) -> None:
    """Track suggestions shown this session to avoid immediate repeats."""
    shown = list(context.working_memory.session_facts.get("shown_suggestions") or [])
    for suggestion in suggestions:
        text = suggestion.strip()
        if text and text not in shown:
            shown.append(text)
    context.working_memory.session_facts["shown_suggestions"] = shown[-30:]


def _executed_date_range(tool_results: list[Any] | None) -> tuple[str | None, str | None]:
    """Pull the actual date range used by the executed tools, if any."""
    for result in reversed(tool_results or []):
        if not isinstance(result, dict):
            continue
        used = result.get("used_context") if isinstance(result.get("used_context"), dict) else {}
        date_from = result.get("date_from") or used.get("date_from")
        date_to = result.get("date_to") or used.get("date_to")
        if date_from and date_to:
            return str(date_from), str(date_to)
    return None, None


def _infer_category(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("compare", "vs", "trend", "last year", "previous period")):
        return "compare"
    if any(word in lower for word in ("filter", "only", "exclude", "group by")):
        return "filter"
    if any(word in lower for word in ("pdf", "excel", "export", "generate")):
        return "export"
    if any(word in lower for word in ("break", "show", "list", "drill", "top")):
        return "drill"
    return "analysis"


def _is_permission_blocked(text: str, context: ContextStack) -> bool:
    lower = text.lower()
    if context.user.level >= 70:
        return False
    blocked_terms = ("all projects", "general ledger", "payroll", "payslip")
    return any(term in lower for term in blocked_terms)

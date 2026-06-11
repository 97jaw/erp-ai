"""Context-aware suggestion generation with category diversity (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent
from gateway.core.proactive_intelligence import PredictedAction, _top_client_from_visualization
from gateway.core.result_synthesizer import SynthesizedResult
from gateway.suggestion_pool import (
    detect_suggestion_context,
    extract_data_context,
    get_suggestion_pool,
    pick_diverse_suggestions,
)

MAX_SUGGESTION_LENGTH = 90
TARGET_COUNT = 3


@dataclass(frozen=True)
class Suggestion:
    """One ranked follow-up suggestion."""

    text: str
    category: str
    priority: int = 0


class SmartSuggestionsGenerator:
    """Build diverse, data-specific suggestions from the current response."""

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
            synthesized,
            intent,
            context,
            tool_names=tool_names,
            tool_results=tool_results,
            predicted_actions=predicted_actions or [],
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
        predicted_actions: list[PredictedAction],
    ) -> list[Suggestion]:
        # Project profile answers get profile chips only — never the expense
        # drill/compare/table pool (those imply Deep Think flows).
        if "get_project_profile" in tool_names:
            return self._project_profile_suggestions(context, tool_results)
        if "get_project_records" in tool_names:
            return self._project_records_suggestions(context, tool_results)
        if "get_project_activity" in tool_names:
            return self._project_activity_suggestions(context, tool_results)

        candidates: list[Suggestion] = []
        candidates.extend(
            Suggestion(text=item.text, category=item.category, priority=item.priority)
            for item in self._predicted_suggestions(predicted_actions)
        )
        candidates.extend(self._context_interpolated_suggestions(context, tool_results))
        candidates.extend(self._drill_down_suggestions(synthesized, intent))
        candidates.extend(self._comparison_suggestions(synthesized, intent))
        candidates.extend(self._action_suggestions(synthesized, tool_names))
        candidates.extend(self._insight_suggestions(synthesized, tool_results))

        suggestion_context = detect_suggestion_context(tool_names, synthesized.visualization)
        data_context = extract_data_context(synthesized.visualization, tool_results)
        for text in get_suggestion_pool(suggestion_context, data_context):
            candidates.append(Suggestion(text=text, category=_infer_category(text)))

        if intent.primary_action == "compare":
            candidates.append(
                Suggestion(
                    text="Compare the same clients for project expenses in the same period.",
                    category="compare",
                ),
            )

        return candidates

    @staticmethod
    def _project_profile_suggestions(
        context: ContextStack,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        """Profile-appropriate follow-ups; expenses is the one Deep Think handoff."""
        project_name = None
        focus = "all"
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("_source") == "project_profile":
                project_name = payload.get("project_name")
                focus = str(payload.get("focus") or "all")
                break
        if not project_name:
            active = context.working_memory.get_active_project()
            project_name = active.project_name if active is not None else "the project"

        suggestions: list[Suggestion] = []
        if focus not in {"schedule", "all"}:
            suggestions.append(
                Suggestion(
                    text=f"Show {project_name} schedule and duration",
                    category="drill",
                    priority=5,
                ),
            )
        if focus != "team":
            suggestions.append(
                Suggestion(
                    text=f"Who is the project manager of {project_name}?",
                    category="drill",
                    priority=4,
                ),
            )
        if focus in {"team", "schedule"}:
            suggestions.append(
                Suggestion(
                    text=f"Show {project_name} engineer amounts",
                    category="drill",
                    priority=4,
                ),
            )
        suggestions.append(
            Suggestion(
                text=f"Show {project_name} expenses",
                category="action",
                priority=3,
            ),
        )
        return [item for item in suggestions if len(item.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _project_records_suggestions(
        context: ContextStack,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        """Record-list follow-ups: sibling record types + date widen + expenses."""
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

        # Staff <-> supervisors cross-suggest; documents cross-suggest each other.
        sibling_by_type = {
            "invoices": [("Show {p} purchase orders", "drill")],
            "client_invoices": [("Show {p} LPO invoices", "drill")],
            "lpo_invoices": [("Show {p} client invoices", "drill")],
            "purchase_orders": [("Show {p} LPO invoices", "drill")],
            "timesheets": [("Show {p} staff list", "drill")],
            "petty_cash": [("Show {p} petty cash sheets", "drill")],
            "petty_cash_sheets": [("Show {p} petty cash expenses", "drill")],
            "staff": [("Show {p} supervisors", "drill")],
            "supervisors": [("Show {p} staff list", "drill")],
        }
        suggestions: list[Suggestion] = []
        for template, category in sibling_by_type.get(record_type, []):
            suggestions.append(
                Suggestion(text=template.format(p=project_name), category=category, priority=5),
            )
        if period_defaulted:
            suggestions.append(
                Suggestion(
                    text=f"Show {project_name} {record_type.replace('_', ' ')} for this year",
                    category="time",
                    priority=4,
                ),
            )
        suggestions.append(
            Suggestion(text=f"Show {project_name} expenses", category="action", priority=3),
        )
        return [item for item in suggestions if len(item.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _project_activity_suggestions(
        context: ContextStack,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        project_name = None
        activity_type = ""
        for payload in tool_results:
            if isinstance(payload, dict) and payload.get("_source") == "project_activity":
                project_name = payload.get("project_name")
                activity_type = str(payload.get("activity_type") or "")
                break
        if not project_name:
            active = context.working_memory.get_active_project()
            project_name = active.project_name if active is not None else "the project"
        siblings = {
            "attachments": [
                (f"Chatter summary of {project_name}", "drill"),
                (f"Progress of {project_name}", "drill"),
            ],
            "chatter_summary": [
                (f"Attachments of {project_name}", "drill"),
                (f"Last updated by for {project_name}", "drill"),
            ],
            "progress": [
                (f"Attachments of {project_name}", "drill"),
                (f"Show {project_name} schedule and duration", "drill"),
            ],
            "audit": [
                (f"Chatter summary of {project_name}", "drill"),
                (f"Progress of {project_name}", "drill"),
            ],
        }
        return [
            Suggestion(text=text, category=cat, priority=5)
            for text, cat in siblings.get(activity_type, [])
        ][:3]

    @staticmethod
    def _context_interpolated_suggestions(
        context: ContextStack,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        """Chips built from the actual entities and date range of this turn."""
        suggestions: list[Suggestion] = []
        date_from, date_to = _executed_date_range(tool_results)
        period_label = f"from {date_from} to {date_to}" if date_from and date_to else ""

        active = context.working_memory.get_active_project()
        project_name = active.project_name if active is not None else None
        if project_name:
            breakdown = f"Break down {project_name} expenses by account"
            if period_label:
                breakdown = f"{breakdown} {period_label}"
            suggestions.append(Suggestion(text=breakdown, category="drill", priority=5))
            suggestions.append(
                Suggestion(
                    text=f"Compare {project_name} expenses with the previous period",
                    category="compare",
                    priority=4,
                ),
            )
        if period_label:
            suggestions.append(
                Suggestion(
                    text=f"Show the P&L {period_label}",
                    category="drill",
                    priority=3,
                ),
            )
        return [item for item in suggestions if len(item.text) <= MAX_SUGGESTION_LENGTH]

    @staticmethod
    def _predicted_suggestions(predicted_actions: list[PredictedAction]) -> list[Suggestion]:
        ranked: list[Suggestion] = []
        for action in sorted(predicted_actions, key=lambda item: item.likelihood, reverse=True):
            text = action.suggestion_text.strip()
            if not text:
                continue
            ranked.append(
                Suggestion(
                    text=text,
                    category=_infer_category(text),
                    priority=max(1, int(action.likelihood * 100)),
                ),
            )
        return ranked

    @staticmethod
    def _drill_down_suggestions(
        synthesized: SynthesizedResult,
        intent: Intent,
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        top_client = _top_client_from_visualization(synthesized.visualization)
        if top_client:
            suggestions.append(
                Suggestion(
                    text=f"Show project expenses for {top_client} last quarter",
                    category="drill",
                    priority=4,
                ),
            )
            suggestions.append(
                Suggestion(
                    text=f"Break down costs by category for {top_client}",
                    category="drill",
                    priority=3,
                ),
            )
        label = str((synthesized.visualization or {}).get("label") or intent.specific_intent)
        if "project" in label.lower():
            suggestions.append(
                Suggestion(
                    text="Show which cost category caused the largest spend",
                    category="drill",
                ),
            )
        return suggestions

    @staticmethod
    def _comparison_suggestions(
        synthesized: SynthesizedResult,
        intent: Intent,
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        top_client = _top_client_from_visualization(synthesized.visualization)
        if intent.primary_action == "compare":
            suggestions.append(
                Suggestion(
                    text="Drill into the biggest revenue change driver",
                    category="analysis",
                ),
            )
        if top_client:
            suggestions.append(
                Suggestion(
                    text=f"Compare {top_client} revenue with last year",
                    category="compare",
                ),
            )
        suggestions.append(
            Suggestion(
                text="Compare with the previous period",
                category="compare",
            ),
        )
        return suggestions

    @staticmethod
    def _action_suggestions(
        synthesized: SynthesizedResult,
        tool_names: list[str],
    ) -> list[Suggestion]:
        visual_type = (synthesized.visualization or {}).get("visual_type") or ""
        suggestions: list[Suggestion] = []
        if visual_type in {"DATA_TABLE", "BAR_CHART", "FINANCIAL_REPORT"}:
            suggestions.append(
                Suggestion(text="Export this view to Excel", category="export"),
            )
        if "get_financial_report" in tool_names or visual_type == "FINANCIAL_REPORT":
            suggestions.append(
                Suggestion(text="Generate executive PDF report", category="export"),
            )
        return suggestions

    @staticmethod
    def _insight_suggestions(
        synthesized: SynthesizedResult,
        tool_results: list[Any],
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        data_context = extract_data_context(synthesized.visualization, tool_results)
        if float(data_context.get("net_profit", 0) or 0) < 0:
            suggestions.append(
                Suggestion(
                    text="Why is this period showing a loss?",
                    category="analysis",
                ),
            )
        if data_context.get("over_budget"):
            suggestions.append(
                Suggestion(
                    text="Show which cost category caused the overrun",
                    category="analysis",
                ),
            )
        rows = ((synthesized.visualization or {}).get("data") or {}).get("rows") or []
        if len(rows) >= 3:
            suggestions.append(
                Suggestion(
                    text="Show revenue trend for the top 3 clients",
                    category="analysis",
                ),
            )
        return suggestions

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
        seen: set[str] = set()

        for candidate in ordered:
            if candidate.priority <= 0:
                break
            if candidate.text in seen:
                continue
            selected.append(candidate)
            seen.add(candidate.text)
            if len(selected) >= target_count:
                return selected[:target_count]

        remaining = [candidate for candidate in ordered if candidate.text not in seen]
        pool = [candidate.text for candidate in remaining]
        category_by_text = {candidate.text: candidate.category for candidate in remaining}
        picked = pick_diverse_suggestions(pool, target_count - len(selected), exclude=seen)
        for text in picked:
            selected.append(
                Suggestion(
                    text=text,
                    category=category_by_text.get(text, _infer_category(text)),
                ),
            )

        for candidate in remaining:
            if len(selected) >= target_count:
                break
            if candidate.text not in {item.text for item in selected}:
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

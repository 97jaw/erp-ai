"""Polish orchestrated responses and revise them through the quality gate."""

from __future__ import annotations

import re
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.failure_handler import HonestFailureResponder
from gateway.core.intent_analyzer import Intent
from gateway.core.quality_gate import (
    QUALITY_CHECKS,
    QualityResponse,
    QualityReview,
)
from gateway.quality_formatting import humanize_aggregate_spec, humanize_group_label
from gateway.quality_response import polish_agent_response

RAW_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"amount_total:sum"), "Revenue"),
    (re.compile(r"amount_total_sum"), "Revenue"),
    (re.compile(r"__count"), "record count"),
    (re.compile(r"partner_id\[?\d*"), "client"),
    (re.compile(r"\[\s*\d+\s*,\s*['\"][^'\"]+['\"]\s*\]"), "the client"),
    (re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"), ""),
)

NO_DATA_PREFIX = "No data found for"

_BREAKDOWN_EMPTY_WITH_SUMMARY_SUFFIX = (
    "Want me to show the trade-category breakdown from the summary instead?"
)


def _primary_tool_name(tool_names: list[str] | None) -> str:
    if not tool_names:
        return ""
    return str(tool_names[0] or "")


def _infer_tool_name_from_results(tool_results: list[Any] | None) -> str:
    source_to_tool = {
        "project_expense_breakdown_mobile": "get_project_expense_breakdown",
        "project_expense_summary_mobile": "get_project_expense_summary",
    }
    for payload in reversed(tool_results or []):
        if not isinstance(payload, dict):
            continue
        source = str(payload.get("_source") or "")
        if source in source_to_tool:
            return source_to_tool[source]
    return ""


def _resolve_tool_name(
    tool_names: list[str] | None,
    tool_results: list[Any] | None,
) -> str:
    return _primary_tool_name(tool_names) or _infer_tool_name_from_results(tool_results)


def _get_strategies_for_context(tool_name: str) -> list[str]:
    """Return context-appropriate strategy descriptions for no-data messaging."""
    lowered = (tool_name or "").lower()
    if "expense" in lowered or "project" in lowered:
        return ["project expense breakdown", "GL group hierarchy"]
    if "financial" in lowered or "ledger" in lowered:
        return ["group_and_aggregate", "posted invoice filters"]
    return ["data search"]


def _project_label_from_context(context: ContextStack | None) -> str | None:
    if context is None:
        return None
    facts = context.working_memory.session_facts
    if facts.get("project_name"):
        return str(facts["project_name"])
    confirmed = facts.get("confirmed_entities") or {}
    project = confirmed.get("project") or {}
    if project.get("name"):
        return str(project["name"])
    return None


def _breakdown_empty_with_prior_summary_message(
    *,
    context: ContextStack | None,
    tool_results: list[Any] | None = None,
) -> str | None:
    """Custom copy when GL breakdown is empty but a prior expense summary exists."""
    if context is None:
        return None
    if not context.working_memory.session_facts.get("last_expense_summary_project_id"):
        return None

    project_name = _project_label_from_context(context)
    if tool_results:
        for payload in reversed(tool_results):
            if not isinstance(payload, dict):
                continue
            if payload.get("_source") != "project_expense_breakdown_mobile":
                continue
            project_name = payload.get("project_name") or project_name
            break

    label = project_name or "this project"
    return (
        f"I found the expense summary for {label}, but the detailed GL breakdown has no data. "
        "This may mean the project expenses haven't been categorized by account group yet in Odoo. "
        f"{_BREAKDOWN_EMPTY_WITH_SUMMARY_SUFFIX}"
    )


def tool_results_from_execution(results: dict[int, Any]) -> list[Any]:
    """Flatten orchestrator step results into a tool result list."""
    return [results[step_number] for step_number in sorted(results.keys())]


def has_meaningful_tool_data(tool_results: list[Any]) -> bool:
    """Return True when tool payloads contain non-zero business values."""
    scalar_keys = (
        "total_expenses",
        "total_cost",
        "total_revenue",
        "net_profit",
        "expense_total",
        "income",
        "balance",
        "amount_total",
    )
    for payload in tool_results:
        if not isinstance(payload, dict) or payload.get("error"):
            continue
        if payload.get("_source") == "search_entities" and payload.get("status") == "success":
            return True
        if payload.get("candidates"):
            return True
        for key in scalar_keys:
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if abs(float(value)) >= 1:
                    return True
        groups = payload.get("groups") or payload.get("rows") or []
        for group in groups:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                if key.startswith("__"):
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if abs(float(value)) >= 1:
                        return True
    return False


def no_data_message(
    intent: Intent,
    *,
    user_message: str = "",
    context: ContextStack | None = None,
    tool_names: list[str] | None = None,
    tool_results: list[Any] | None = None,
) -> str:
    """Honest empty-data response — never fabricate figures."""
    tool_name = _resolve_tool_name(tool_names, tool_results)
    if tool_name == "get_project_expense_breakdown":
        summary_message = _breakdown_empty_with_prior_summary_message(
            context=context,
            tool_results=tool_results,
        )
        if summary_message:
            return summary_message

    responder = HonestFailureResponder()
    failure = HonestFailureResponder.failure_from_no_data(
        intent,
        user_message or intent.specific_intent,
        strategies_tried=_get_strategies_for_context(tool_name),
    )
    stack = context or _minimal_context(user_message or intent.specific_intent)
    return responder.respond(failure, stack).text


def _minimal_context(message: str) -> ContextStack:
    from gateway.core.business_context import BusinessContext
    from gateway.core.capability_manifest import CAPABILITY_MANIFEST
    from gateway.core.context_stack import ConversationContext, ContextStack, QualityTargets
    from gateway.core.temporal_context import TemporalContext
    from gateway.core.user_context import UserContext
    from gateway.core.working_memory import WorkingMemory

    return ContextStack(
        user=UserContext(
            user_id=0,
            name="User",
            file_id="",
            primary_role="regular_user",
            level=30,
            permissions=set(),
            primary_department="General",
            departments=["General"],
            preferred_language="en",
            preferred_currency="AED",
            default_date_range="last_3_months",
            response_style="brief",
            last_login=TemporalContext.build().now,
            typical_queries=[],
        ),
        conversation=ConversationContext(session_id=None, message=message),
        capability_manifest=CAPABILITY_MANIFEST,
        working_memory=WorkingMemory(),
        business_context=BusinessContext(),
        temporal_context=TemporalContext.build(),
        quality_targets=QualityTargets(),
    )


def default_suggestions(intent: Intent) -> list[str]:
    """Provide actionable follow-ups when the response lacks suggestions."""
    if intent.primary_action == "compare":
        return ["Compare the same clients for project expenses in the same period."]
    return ["Show revenue by client for the last quarter."]


def strip_raw_syntax(text: str) -> str:
    """Remove raw Odoo syntax from user-facing narrative text."""
    cleaned = text
    for pattern, replacement in RAW_TEXT_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def polish_execution_response(
    *,
    message: str,
    text: str,
    visualization: dict[str, Any] | None,
    tool_names: list[str],
    tool_results: list[Any],
    language: str,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Apply existing polish layer and attach default suggestions."""
    polished_text, polished_visual = polish_agent_response(
        message,
        text,
        visualization,
        tool_names,
        tool_results,
        language,
    )
    return polished_text, polished_visual, []


def build_quality_response(
    *,
    message: str,
    text: str,
    visualization: dict[str, Any] | None,
    tool_names: list[str],
    tool_results: list[Any],
    language: str,
    intent: Intent,
    context: ContextStack | None = None,
    suggestions: list[str] | None = None,
) -> QualityResponse:
    """Build a polished payload ready for quality gate review."""
    if not has_meaningful_tool_data(tool_results):
        honest_text = no_data_message(
            intent,
            user_message=message,
            context=context,
            tool_names=tool_names,
            tool_results=tool_results,
        )
        return QualityResponse(
            text=honest_text,
            visualization=None,
            suggestions=suggestions or default_suggestions(intent),
            tool_results=tool_results,
        )

    polished_text, polished_visual, _ = polish_execution_response(
        message=message,
        text=text,
        visualization=visualization,
        tool_names=tool_names,
        tool_results=tool_results,
        language=language,
    )
    final_suggestions = suggestions or default_suggestions(intent)
    return QualityResponse(
        text=polished_text,
        visualization=polished_visual,
        suggestions=final_suggestions,
        tool_results=tool_results,
    )


class QualityResponseReviser:
    """Deterministically revise responses that fail quality checks."""

    async def __call__(
        self,
        response: QualityResponse,
        review: QualityReview,
        intent: Intent,
        context: ContextStack,
    ) -> QualityResponse:
        failed_names = {check.name for check in review.checks if not check.passed}
        text = response.text
        visualization = response.visualization
        suggestions = list(response.suggestions)
        tool_results = response.tool_results

        if not has_meaningful_tool_data(tool_results):
            text = no_data_message(
                intent,
                user_message=response.text,
                context=context,
                tool_results=tool_results,
            )
            visualization = None
        elif "no_fabrication" in failed_names:
            text = strip_raw_syntax(text)

        if "no_raw_syntax" in failed_names or "clear_language" in failed_names:
            text = strip_raw_syntax(text)
            if visualization:
                visualization = _humanize_visualization(visualization)

        if "data_consistency" in failed_names and visualization:
            visualization = None
            text = (
                f"{text} Some figures may be inconsistent — "
                "please verify the underlying Odoo records."
            )

        if "honest_about_uncertainty" in failed_names:
            text = (
                f"{text} The available data may be incomplete for this period."
            ).strip()

        if "actionable_suggestions" in failed_names:
            suggestions = default_suggestions(intent)

        if "appropriate_detail" in failed_names and len(text) < 25:
            text = (
                f"Summary for {intent.specific_intent}: {text} "
                "Figures come from posted Odoo records for the requested period."
            ).strip()

        if "right_visualization" in failed_names and visualization is None and has_meaningful_tool_data(tool_results):
            _, visualization, _ = polish_execution_response(
                message=intent.specific_intent,
                text=text,
                visualization=None,
                tool_names=["group_and_aggregate"],
                tool_results=tool_results,
                language="en",
            )

        if "not_all_zero" in failed_names:
            from gateway.core.quality_gate import build_zero_data_honest_message

            text = build_zero_data_honest_message(response, intent)
            if not suggestions:
                suggestions = [
                    "Search for a different project name or WO number.",
                    "Show related projects that may match what you meant.",
                ]

        if "no_contradictions" in failed_names:
            from gateway.quality_narrative import generate_narrative

            regenerated = generate_narrative(
                intent.specific_intent,
                visualization,
                tool_results,
                language="en",
            )
            if regenerated:
                text = regenerated

        return QualityResponse(
            text=strip_raw_syntax(text),
            visualization=visualization,
            suggestions=suggestions,
            tool_results=tool_results,
        )


def _humanize_visualization(visualization: dict[str, Any]) -> dict[str, Any]:
    polished = dict(visualization)
    data = dict(polished.get("data") or {})
    headers = data.get("headers") or []
    if headers:
        data["headers"] = [humanize_aggregate_spec(str(header)) for header in headers]
    rows = data.get("rows") or []
    cleaned_rows = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        cleaned_rows.append([humanize_group_label(cell) if index == 0 else cell for index, cell in enumerate(row)])
    data["rows"] = cleaned_rows
    polished["data"] = data
    return polished


def quality_gate_log_message(review: QualityReview) -> str:
    """Format a log line for quality gate outcomes."""
    passed_count = sum(1 for check in review.checks if check.passed)
    total = len(review.checks) or len(QUALITY_CHECKS)
    return f"Quality gate: {passed_count}/{total} checks passed"

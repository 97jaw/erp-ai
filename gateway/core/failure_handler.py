"""Honest failure responses — never fabricate excuses (Phase 6)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from gateway.core.capability_manifest import CAPABILITY_MANIFEST, Capability
from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

FABRICATION_PHRASES = (
    "database issue",
    "database error",
    "temporary error",
    "try again later",
    "try again",
    "connection issue",
    "system error",
    "operation in progress",
    "please retry",
)


class FailureMode(str, Enum):
    """All ways the assistant can fail to fulfill a request."""

    TOOL_NOT_AVAILABLE = "tool_not_available"
    FEATURE_COMING_SOON = "feature_coming_soon"
    OUT_OF_SCOPE = "out_of_scope"
    NO_DATA_FOUND = "no_data_found"
    DATA_INCOMPLETE = "data_incomplete"
    DATA_AMBIGUOUS = "data_ambiguous"
    PERMISSION_DENIED = "permission_denied"
    DEPARTMENT_RESTRICTED = "department_restricted"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    INVALID_PERIOD = "invalid_period"
    UNCLEAR_INTENT = "unclear_intent"


@dataclass
class Failure:
    """Structured failure context for response generation."""

    mode: FailureMode
    user_message: str = ""
    capability_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureResponse:
    """User-facing honest failure payload."""

    text: str
    suggestions: list[str] = field(default_factory=list)
    failure_mode: FailureMode = FailureMode.OUT_OF_SCOPE


@dataclass(frozen=True)
class _FailureTemplate:
    """Template metadata and body for one failure mode."""

    tone: str
    body: str
    never: str = ""
    default_suggestions: tuple[str, ...] = ()


class HonestFailureResponder:
    """Generate honest, helpful responses for each failure mode."""

    RESPONSE_TEMPLATES: dict[FailureMode, _FailureTemplate] = {
        FailureMode.TOOL_NOT_AVAILABLE: _FailureTemplate(
            tone="honest, helpful",
            body=(
                "{capability_label} isn't available in this assistant yet"
                "{roadmap_clause}. "
                "{alternative_clause}"
                "{notify_clause}"
            ),
            never="Don't say 'database issue', 'temporary error', or 'try again'",
            default_suggestions=(
                "Show me project financials I can access today.",
                "What financial reports are available in this assistant?",
            ),
        ),
        FailureMode.FEATURE_COMING_SOON: _FailureTemplate(
            tone="honest, forward-looking",
            body=(
                "{capability_label} is planned but not live yet{eta_clause}. "
                "{alternative_clause}"
                "{workaround_clause}"
            ),
            never="Don't promise a result you cannot deliver now",
            default_suggestions=(
                "Show historical cash flow trends instead.",
                "Compare revenue across the last two quarters.",
            ),
        ),
        FailureMode.OUT_OF_SCOPE: _FailureTemplate(
            tone="direct, honest",
            body=(
                "I can't help with that request in this assistant. "
                "{reason_clause}"
                "{alternative_clause}"
            ),
            never="Don't invent system errors or ask the user to retry",
            default_suggestions=(),  # No suggestions — empty is better than wrong for out-of-scope
        ),
        FailureMode.NO_DATA_FOUND: _FailureTemplate(
            tone="honest, exploratory",
            body=(
                "No data found for {query_label}. "
                "{effort_clause}"
                "{suggest_clause}"
            ),
            never="Don't pretend to have searched if no tools ran",
            default_suggestions=(
                "Try a wider date range for the same question.",
                "Search projects by client name instead.",
            ),
        ),
        FailureMode.DATA_INCOMPLETE: _FailureTemplate(
            tone="transparent",
            body=(
                "I found partial data for {query_label}, but the result is incomplete. "
                "{detail_clause}"
                "I won't fill in missing figures — tell me if you want a narrower slice retried."
            ),
            never="Don't extrapolate or estimate missing values",
            default_suggestions=(
                "Retry with a shorter date range.",
                "Break the request into one client or one project.",
            ),
        ),
        FailureMode.DATA_AMBIGUOUS: _FailureTemplate(
            tone="careful",
            body=(
                "The data for {query_label} is ambiguous — multiple records match and "
                "the totals may double-count. {detail_clause}"
                "Please narrow the client, project, or period."
            ),
            never="Don't pick a single total without explaining ambiguity",
            default_suggestions=(
                "Filter to one project name or WO reference.",
                "Compare clients separately instead of combined totals.",
            ),
        ),
        FailureMode.PERMISSION_DENIED: _FailureTemplate(
            tone="respectful, clear",
            body=(
                "Your current role doesn't include access to {data_type}. "
                "{permission_clause}"
                "{action_clause}"
            ),
            never="Don't share restricted values before refusing",
            default_suggestions=(
                "Show data available for my role instead.",
                "Summarize projects in my department only.",
            ),
        ),
        FailureMode.DEPARTMENT_RESTRICTED: _FailureTemplate(
            tone="respectful",
            body=(
                "That request spans data outside your department scope ({department}). "
                "I can only show records for departments you are authorized to view."
            ),
            never="Don't leak cross-department figures",
            default_suggestions=(
                "Show projects in my department.",
                "Summarize financials for my assigned clients.",
            ),
        ),
        FailureMode.TOOL_ERROR: _FailureTemplate(
            tone="honest, practical",
            body=(
                "Something went wrong while calling {tool_name}. "
                "{error_clause}"
                "{action_clause}"
            ),
            never="Don't blame a generic database outage unless that was the actual error",
            default_suggestions=(
                "Retry with a narrower date range.",
                "Ask for a project summary instead of a detailed ledger pull.",
            ),
        ),
        FailureMode.TIMEOUT: _FailureTemplate(
            tone="honest",
            body=(
                "That query took too long to complete against Odoo. "
                "Try a shorter period, fewer groupings, or a single project/client filter."
            ),
            never="Don't ask the user to keep retrying the same heavy query unchanged",
            default_suggestions=(
                "Limit the request to the last month.",
                "Show top 5 clients only.",
            ),
        ),
        FailureMode.SERVICE_UNAVAILABLE: _FailureTemplate(
            tone="honest",
            body=(
                "Odoo or a required backend service isn't responding right now. "
                "This is a connectivity issue — not missing data in your request. "
                "Please check back once the service is restored."
            ),
            never="Don't confuse service outage with unavailable capability",
            default_suggestions=(
                "Check project summaries once the service is back.",
            ),
        ),
        FailureMode.AMBIGUOUS_REFERENCE: _FailureTemplate(
            tone="helpful, decisive",
            body=(
                "I found {match_count} possible matches for '{query_label}'. "
                "{matches_clause}"
                "{decision_clause}"
            ),
            never="Don't ask regular users vague clarification when a top match is obvious",
            default_suggestions=tuple(),
        ),
        FailureMode.INVALID_PERIOD: _FailureTemplate(
            tone="helpful",
            body=(
                "The period '{period_label}' isn't valid for this query. "
                "{detail_clause}"
                "Use a concrete range such as last quarter, YTD, or explicit dates."
            ),
            never="Don't silently substitute a different period without saying so",
            default_suggestions=(
                "Show revenue for the last quarter instead.",
                "Use year-to-date figures.",
            ),
        ),
        FailureMode.UNCLEAR_INTENT: _FailureTemplate(
            tone="collaborative",
            body=(
                "I'm not sure what you need yet. "
                "{detail_clause}"
                "Tell me whether you want financial reports, project costs, or client revenue."
            ),
            never="Don't run tools until intent is clear enough",
            default_suggestions=(
                "Show P&L for the last 3 months.",
                "List top projects by cost this year.",
            ),
        ),
    }

    def respond(self, failure: Failure, context: ContextStack) -> FailureResponse:
        """Craft an honest failure response for the given mode."""
        if (
            failure.mode == FailureMode.NO_DATA_FOUND
            and failure.details.get("entity_not_found")
        ):
            query_label = str(
                failure.details.get("query_label") or failure.user_message or "that project"
            ).strip()
            text = self._entity_not_found_message(query_label)
            suggestions = [
                "Search by Work Order number",
                "Try a different spelling of the project name",
            ]
            return FailureResponse(
                text=text,
                suggestions=suggestions,
                failure_mode=failure.mode,
            )
        template = self.RESPONSE_TEMPLATES[failure.mode]
        text = self._render(template.body, failure, context).strip()
        text = self._clean_text(text)
        suggestions = list(failure.details.get("suggestions") or template.default_suggestions)
        if failure.mode == FailureMode.AMBIGUOUS_REFERENCE and failure.details.get("match_suggestions"):
            suggestions = list(failure.details["match_suggestions"])[:3]
        return FailureResponse(text=text, suggestions=suggestions, failure_mode=failure.mode)

    @staticmethod
    def _entity_not_found_message(query_label: str) -> str:
        """User-facing copy when entity discovery finds no project/partner."""
        return (
            f"I couldn't find a project matching '{query_label}' in the system.\n\n"
            "Try:\n"
            "• A different spelling\n"
            "• The Work Order number\n"
            "• The client name\n\n"
            "Or I can search more broadly."
        )

    @classmethod
    def failure_from_intent(cls, intent: Intent, user_message: str) -> Failure:
        """Map an out-of-scope intent to a structured failure."""
        capability_code = cls._capability_code_from_intent(intent, user_message)
        if capability_code and CAPABILITY_MANIFEST.status_of(capability_code) == "coming_soon":
            return Failure(
                mode=FailureMode.FEATURE_COMING_SOON,
                user_message=user_message,
                capability_code=capability_code,
                details={"reason": intent.out_of_scope_reason or ""},
            )
        if capability_code and CAPABILITY_MANIFEST.status_of(capability_code) == "unavailable":
            return Failure(
                mode=FailureMode.TOOL_NOT_AVAILABLE,
                user_message=user_message,
                capability_code=capability_code,
                details={"reason": intent.out_of_scope_reason or ""},
            )
        return Failure(
            mode=FailureMode.OUT_OF_SCOPE,
            user_message=user_message,
            details={"reason": intent.out_of_scope_reason or intent.specific_intent},
        )

    @classmethod
    def failure_from_no_data(cls, intent: Intent, user_message: str, *, strategies_tried: list[str] | None = None) -> Failure:
        query_label = (
            (intent.specific_intent or "").strip()
            or (user_message or "").strip()
            or "that request"
        )
        return Failure(
            mode=FailureMode.NO_DATA_FOUND,
            user_message=user_message,
            details={
                "query_label": query_label,
                "strategies_tried": strategies_tried or [],
                "subject_area": intent.subject_area,
            },
        )

    @classmethod
    def failure_from_stage(
        cls,
        stage: str,
        exc: Exception,
        user_message: str,
    ) -> Failure | None:
        """Map a pipeline stage exception to an honest failure mode.

        For entity_resolution, never returns DATA_AMBIGUOUS. needs_confirm is not
        a failure — callers should route clarification before invoking this helper.
        """
        from gateway.core.execution_orchestrator import OrchestrationException
        from gateway.core.intent_analyzer import AnalyzerException
        from gateway.core.strategy_planner import StrategyException

        error_summary = str(exc).strip() or exc.__class__.__name__
        details: dict[str, Any] = {"stage": stage, "error_summary": error_summary}

        if isinstance(exc, AnalyzerException):
            return Failure(
                mode=FailureMode.UNCLEAR_INTENT,
                user_message=user_message,
                details=details,
            )
        if isinstance(exc, StrategyException):
            return Failure(
                mode=FailureMode.TOOL_ERROR,
                user_message=user_message,
                details=details,
            )
        if isinstance(exc, OrchestrationException):
            error_summary = str(exc).strip() or exc.__class__.__name__
            if "Missing permission" in error_summary:
                return Failure(
                    mode=FailureMode.PERMISSION_DENIED,
                    user_message=user_message,
                    details={**details, "error_summary": error_summary},
                )
            return Failure(
                mode=FailureMode.TOOL_ERROR,
                user_message=user_message,
                details=details,
            )
        if isinstance(exc, TimeoutError):
            return Failure(
                mode=FailureMode.TIMEOUT,
                user_message=user_message,
                details=details,
            )
        if stage in {"context", "telemetry"}:
            return Failure(
                mode=FailureMode.SERVICE_UNAVAILABLE,
                user_message=user_message,
                details=details,
            )
        if stage == "entity_resolution":
            return cls.failure_from_entity_resolution(
                cls._entity_resolution_outcome_from_exception(exc),
                user_message,
                exc=exc,
                query_label=user_message,
            )
        return Failure(
            mode=FailureMode.TOOL_ERROR,
            user_message=user_message,
            details=details,
        )

    @classmethod
    def failure_from_entity_resolution(
        cls,
        outcome: str,
        user_message: str,
        *,
        exc: Exception | None = None,
        query_label: str | None = None,
        matches: list[dict[str, Any]] | None = None,
    ) -> Failure | None:
        """Map entity gate outcomes to failure modes.

        Outcomes:
        - needs_confirm / needs_confirmation → None (clarification flow, not a failure)
        - not_found → NO_DATA_FOUND
        - ambiguous → AMBIGUOUS_REFERENCE
        - exception / tool_error → TOOL_ERROR

        DATA_AMBIGUOUS is never returned from entity resolution.
        """
        normalized = outcome.strip().lower()
        if normalized in {"needs_confirm", "needs_confirmation", "weak_confirmation", "confirmed"}:
            return None
        if normalized in {"not_found", "no_data", "no_data_found"}:
            return cls.failure_from_entity_not_found(
                user_message,
                query_label=query_label or user_message,
            )
        if normalized == "ambiguous":
            return cls.failure_from_ambiguous_entities(
                user_message,
                matches or [],
            )
        error_summary = str(exc).strip() if exc else "entity resolution failed"
        if not error_summary:
            error_summary = exc.__class__.__name__ if exc else "entity resolution failed"
        return Failure(
            mode=FailureMode.TOOL_ERROR,
            user_message=user_message,
            details={
                "stage": "entity_resolution",
                "error_summary": error_summary,
            },
        )

    @staticmethod
    def _entity_resolution_outcome_from_exception(exc: Exception) -> str:
        """Infer entity gate outcome from a raised exception message."""
        message = str(exc).strip().lower()
        if not message:
            return "exception"
        not_found_markers = (
            "no matching",
            "not found",
            "no project",
            "no partner",
            "no usable",
            "zero matches",
        )
        ambiguous_markers = (
            "ambiguous",
            "multiple matches",
            "multiple records",
            "more than one",
        )
        if any(marker in message for marker in not_found_markers):
            return "not_found"
        if any(marker in message for marker in ambiguous_markers):
            return "ambiguous"
        return "exception"

    @classmethod
    def failure_from_entity_not_found(
        cls,
        user_message: str,
        *,
        query_label: str,
    ) -> Failure:
        """Build a failure when entity discovery finds no usable project/partner."""
        return Failure(
            mode=FailureMode.NO_DATA_FOUND,
            user_message=user_message,
            details={
                "query_label": query_label,
                "entity_not_found": True,
            },
        )

    @classmethod
    def failure_from_ambiguous_entities(
        cls,
        user_message: str,
        matches: list[dict[str, Any]],
    ) -> Failure:
        """Build a failure when entity resolution needs user disambiguation."""
        return Failure(
            mode=FailureMode.AMBIGUOUS_REFERENCE,
            user_message=user_message,
            details={
                "matches": matches,
                "query_label": user_message,
                "match_count": len(matches),
            },
        )

    @staticmethod
    def _capability_code_from_intent(intent: Intent, user_message: str) -> str | None:
        blob = f"{intent.subject_area} {intent.specific_intent} {user_message}".lower()
        if any(token in blob for token in ("payslip", "pay slip", "salary slip", "payroll")):
            return "hr.payslips"
        if "attendance" in blob:
            return "hr.attendance"
        if "leave balance" in blob or "leave request" in blob:
            return "hr.leave_balance"
        if "inventory" in blob or "stock level" in blob:
            return "inventory.stock"
        if "forecast" in blob:
            return "forecasting.cash_flow"
        if intent.out_of_scope_reason and "hr.payslips" in intent.out_of_scope_reason:
            return "hr.payslips"
        return None

    @staticmethod
    def _lookup_capability(code: str | None) -> Capability | None:
        if not code:
            return None
        for bucket in (
            CAPABILITY_MANIFEST.available,
            CAPABILITY_MANIFEST.unavailable,
            CAPABILITY_MANIFEST.coming_soon,
        ):
            for capability in bucket:
                if capability.code == code:
                    return capability
        return None

    def _render(self, body: str, failure: Failure, context: ContextStack) -> str:
        capability = self._lookup_capability(failure.capability_code)
        details = failure.details
        query_label = str(details.get("query_label") or failure.user_message or "that request").strip()
        replacements = {
            "capability_label": capability.description if capability else "That capability",
            "roadmap_clause": self._roadmap_clause(capability),
            "alternative_clause": self._alternative_clause(capability, details.get("reason")),
            "notify_clause": self._notify_clause(failure.mode),
            "eta_clause": self._eta_clause(capability),
            "workaround_clause": self._workaround_clause(failure.mode),
            "reason_clause": self._reason_clause(details.get("reason")),
            "query_label": query_label,
            "effort_clause": self._effort_clause(details.get("strategies_tried") or []),
            "suggest_clause": self._suggest_clause(
                details.get("fuzzy_matches") or [],
                subject_area=str(details.get("subject_area") or ""),
            ),
            "detail_clause": self._detail_clause(details.get("detail") or details.get("reason") or ""),
            "data_type": str(details.get("data_type") or "that data"),
            "permission_clause": self._permission_clause(details.get("required_permission")),
            "action_clause": self._action_clause(context, details.get("admin_role")),
            "department": str(details.get("department") or context.user.primary_department),
            "tool_name": str(details.get("tool_name") or "the requested tool"),
            "error_clause": self._error_clause(details.get("error_summary"), context),
            "match_count": str(details.get("match_count") or len(details.get("matches") or [])),
            "matches_clause": self._matches_clause(details.get("matches") or []),
            "decision_clause": self._decision_clause(context, details.get("matches") or []),
            "period_label": str(details.get("period_label") or query_label),
        }
        rendered = body.format(**replacements)
        return rendered

    @staticmethod
    def _clean_text(text: str) -> str:
        cleaned = re.sub(r"\s{2,}", " ", text)
        cleaned = re.sub(r"\s+\.", ".", cleaned)
        return cleaned.strip()

    @staticmethod
    def _roadmap_clause(capability: Capability | None) -> str:
        if capability and capability.roadmap:
            return f" — it's on the roadmap for {capability.roadmap}"
        if capability and capability.eta:
            return f" — expected {capability.eta}"
        return ""

    @staticmethod
    def _alternative_clause(capability: Capability | None, reason: str | None) -> str:
        if capability and capability.alternative:
            return f"For now, {capability.alternative}. "
        if reason and "portal" in reason.lower():
            return f"{reason.strip()} "
        return ""

    @staticmethod
    def _notify_clause(mode: FailureMode) -> str:
        if mode == FailureMode.TOOL_NOT_AVAILABLE:
            return "Want me to notify you when it's ready here?"
        return ""

    @staticmethod
    def _eta_clause(capability: Capability | None) -> str:
        if capability and capability.eta:
            return f" (expected {capability.eta})"
        if capability and capability.roadmap:
            return f" (roadmap: {capability.roadmap})"
        return ""

    @staticmethod
    def _workaround_clause(mode: FailureMode) -> str:
        if mode == FailureMode.FEATURE_COMING_SOON:
            return "In the meantime, I can show related historical trends that are available now."
        return ""

    @staticmethod
    def _reason_clause(reason: str | None) -> str:
        if reason:
            return f"{reason.strip()} "
        return ""

    @staticmethod
    def _effort_clause(strategies: list[str]) -> str:
        if not strategies:
            return "I queried Odoo with your filters but nothing matched. "
        joined = "; ".join(strategies[:3])
        return f"I searched using: {joined}. "

    @staticmethod
    def _suggest_clause(matches: list[str], *, subject_area: str = "") -> str:
        if not matches:
            if subject_area == "financial":
                # Company-wide report — never suggest checking client/project spelling.
                return (
                    "Try a different reporting period, or check that the period "
                    "has posted entries in Odoo."
                )
            return "Try a wider date range or confirm spelling of the client or project name."
        preview = ", ".join(matches[:3])
        return f"Did you mean: {preview}?"

    @staticmethod
    def _detail_clause(detail: str) -> str:
        if detail:
            return f"{detail.strip()} "
        return ""

    @staticmethod
    def _permission_clause(required_permission: str | None) -> str:
        if required_permission:
            return f"This requires {required_permission}. "
        return ""

    @staticmethod
    def _action_clause(context: ContextStack, admin_role: str | None) -> str:
        role = admin_role or "your system administrator"
        if context.user.level >= 70:
            return f"If you need broader access, contact {role}."
        return f"Contact {role} to request access."

    @staticmethod
    def _error_clause(error_summary: str | None, context: ContextStack) -> str:
        if not error_summary:
            return "The tool returned an error before usable data was available. "
        if context.user.level >= 50:
            return f"Error summary: {error_summary}. "
        return "The underlying tool reported an error. "

    @staticmethod
    def _matches_clause(matches: list[Any]) -> str:
        if not matches:
            return "Please provide a more specific name or WO reference."
        lines: list[str] = []
        for match in matches[:3]:
            if isinstance(match, dict):
                label = match.get("name") or match.get("label") or str(match)
                extra = match.get("detail") or match.get("wo_ref_no") or match.get("client")
                if extra:
                    lines.append(f"• {label} ({extra})")
                else:
                    lines.append(f"• {label}")
            else:
                lines.append(f"• {match}")
        return " ".join(lines)

    @staticmethod
    def _decision_clause(context: ContextStack, matches: list[Any]) -> str:
        if not matches:
            return ""
        top = matches[0]
        top_label = top.get("name") if isinstance(top, dict) else str(top)
        if context.user.assumption_level() == "aggressive":
            return f"I'll use {top_label} unless you say otherwise."
        return "Which one did you mean?"


def contains_fabricated_excuse(text: str) -> bool:
    """Return True when text uses forbidden fabricated failure language."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in FABRICATION_PHRASES)

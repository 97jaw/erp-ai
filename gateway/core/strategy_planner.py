"""Strategy planning models and Claude-backed planner for the reasoning engine."""

from __future__ import annotations

import json
import logging
import re
import calendar
from dataclasses import asdict, dataclass, field
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.project_query_utils import looks_like_project_cost_query
from gateway.tool_validation import extract_project_id_from_text
from gateway.core.intent_analyzer import (
    AnthropicJsonClient,
    Intent,
    JsonCompletionClient,
)

logger = logging.getLogger(__name__)

STRATEGY_PLANNER_MODEL = "claude-sonnet-4-20250514"
STRATEGY_PLANNER_MAX_TOKENS = 2048

# Company-wide financial report names → (tool, report_type). Used both for the
# misroute guardrail and the simple-tool resolver.
_COMPANY_REPORT_PATTERNS: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
    (
        re.compile(r"p\s*&\s*l|\bpandl\b|\bpnl\b|profit\s+(and|&)\s+loss|income\s+statement", re.IGNORECASE),
        "get_financial_report",
        "pandl",
    ),
    (re.compile(r"balance\s+sheet", re.IGNORECASE), "get_financial_report", "balance_sheet"),
    (re.compile(r"cash\s*flow\s+(statement|report)|cash\s*flow\b", re.IGNORECASE), "get_financial_report", "cash_flow"),
    (re.compile(r"trial\s+balance", re.IGNORECASE), "get_trial_balance", None),
)

_EXPLICIT_RANGE_RE = re.compile(
    r"from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_LAST_N_MONTHS_RE = re.compile(r"(?:last|past)\s+(\d+)\s+months?", re.IGNORECASE)

_MONTH_YEAR_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s*,?\s*(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _month_year_date_range(blob: str) -> tuple[str, str] | None:
    match = _MONTH_YEAR_RE.search(blob)
    if not match:
        return None
    month_num = _MONTH_NUM.get(match.group(1)[:3].lower())
    if not month_num:
        return None
    year = int(match.group(2))
    last_day = calendar.monthrange(year, month_num)[1]
    return f"{year:04d}-{month_num:02d}-01", f"{year:04d}-{month_num:02d}-{last_day:02d}"


def resolve_report_date_range(query: str, temporal: Any) -> tuple[str, str]:
    """Map a period phrase in the query to (date_from, date_to).

    Falls back to last 3 months when no period is named — the product default.
    """
    blob = (query or "").lower()

    explicit = _EXPLICIT_RANGE_RE.search(blob)
    if explicit:
        return explicit.group(1), explicit.group(2)

    month_year = _month_year_date_range(blob)
    if month_year:
        return month_year

    if "this month" in blob:
        today = temporal.today
        return today.replace(day=1).isoformat(), today.isoformat()
    if "last month" in blob:
        return temporal.last_month
    if "last quarter" in blob:
        return temporal.last_quarter
    if "last year" in blob:
        return temporal.last_year
    if "this year" in blob or "ytd" in blob or "year to date" in blob:
        return temporal.ytd

    n_months = _LAST_N_MONTHS_RE.search(blob)
    if n_months:
        months = max(1, min(int(n_months.group(1)), 36))
        from datetime import timedelta

        start = temporal.today - timedelta(days=30 * months)
        return start.isoformat(), temporal.today.isoformat()

    return temporal.last_3_months


def match_company_report(query: str) -> tuple[str, str | None] | None:
    """Return (tool, report_type) when the query names a company-wide report."""
    blob = (query or "").lower()
    for pattern, tool, report_type in _COMPANY_REPORT_PATTERNS:
        if pattern.search(blob):
            return tool, report_type
    return None


class StrategyException(Exception):
    """Raised when strategy planning cannot proceed."""


@dataclass
class ExecutionStep:
    """One executable step in a multi-step strategy."""

    step_number: int
    description: str
    tool: str
    tool_input: dict[str, Any]
    depends_on: list[int] = field(default_factory=list)
    parallel_with: list[int] = field(default_factory=list)
    expected_output: str = "summary"
    fallback_if_fails: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionStep:
        """Build an ExecutionStep from Claude JSON output."""
        return cls(
            step_number=int(data["step_number"]),
            description=str(data["description"]),
            tool=str(data["tool"]),
            tool_input=dict(data.get("tool_input") or {}),
            depends_on=[int(value) for value in data.get("depends_on") or []],
            parallel_with=[int(value) for value in data.get("parallel_with") or []],
            expected_output=str(data.get("expected_output", "summary")),
            fallback_if_fails=str(data.get("fallback_if_fails") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return asdict(self)


@dataclass
class Strategy:
    """Execution plan for fulfilling an analyzed intent."""

    steps: list[ExecutionStep]
    synthesis_approach: str
    quality_checks: list[str]
    estimated_duration_ms: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Strategy:
        """Build a Strategy from Claude JSON output."""
        steps = [
            ExecutionStep.from_dict(step)
            for step in data.get("steps") or []
            if isinstance(step, dict)
        ]
        if not steps:
            raise StrategyException("Strategy must contain at least one execution step")
        for step in steps:
            if not step.fallback_if_fails:
                raise StrategyException(
                    f"Step {step.step_number} is missing fallback_if_fails",
                )
        quality_checks = [str(item) for item in data.get("quality_checks") or []]
        if not quality_checks:
            raise StrategyException("Strategy quality_checks must be non-empty")
        return cls(
            steps=steps,
            synthesis_approach=str(data.get("synthesis_approach") or ""),
            quality_checks=quality_checks,
            estimated_duration_ms=int(data.get("estimated_duration_ms") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return {
            "steps": [step.to_dict() for step in self.steps],
            "synthesis_approach": self.synthesis_approach,
            "quality_checks": list(self.quality_checks),
            "estimated_duration_ms": self.estimated_duration_ms,
        }


class StrategyPlanner:
    """Plan single-step or multi-step execution strategies for an intent."""

    def __init__(
        self,
        client: JsonCompletionClient | None = None,
        model: str = STRATEGY_PLANNER_MODEL,
    ) -> None:
        self._client = client or AnthropicJsonClient()
        self._model = model

    async def plan(self, intent: Intent, context: ContextStack) -> Strategy:
        """Return an execution strategy for the analyzed intent."""
        self._validate_intent(intent)
        if intent.out_of_scope:
            raise StrategyException(
                "Cannot plan strategy for out-of-scope intent: "
                f"{intent.out_of_scope_reason or 'capability unavailable'}",
            )

        company_report = self._plan_company_report_if_applicable(intent, context)
        if company_report is not None:
            strategy = company_report
        elif self._is_relationship_composition_query(intent):
            strategy = await self.plan_complex(intent, context)
        elif self._resolve_universal_read_tool(intent, context) is not None:
            strategy = self.plan_simple(intent, context)
        elif intent.primary_action == "search_entity" or self._needs_project_entity_search(
            intent,
            context,
        ):
            strategy = self.plan_entity_search(intent, context)
        elif self._is_revenue_by_client_comparison(intent):
            strategy = self.plan_revenue_comparison(intent, context)
        elif self._is_revenue_by_client_period(intent):
            strategy = self.plan_revenue_by_client(intent, context)
        elif self._is_project_cost_query(intent, context):
            strategy = self.plan_simple(intent, context)
        elif intent.estimated_complexity == "simple" and self._single_tool_needed(intent):
            strategy = self.plan_simple(intent, context)
        else:
            strategy = await self.plan_complex(intent, context)

        logger.info(
            "[StrategyPlanner] intent=%r steps=%d duration_ms=%d",
            intent.specific_intent,
            len(strategy.steps),
            strategy.estimated_duration_ms,
        )
        return strategy

    def _plan_company_report_if_applicable(
        self,
        intent: Intent,
        context: ContextStack,
    ) -> Strategy | None:
        """Force the financial-report tool when the user named a company-wide report.

        Guards against LLM intent misclassification (e.g. search_entity/complex)
        sending a P&L query into entity search, which yields a bogus
        'No data found' instead of the report.
        """
        blob = f"{intent.specific_intent} {context.conversation.message}"
        matched = match_company_report(blob)
        if matched is None:
            return None
        if intent.primary_action == "compare":
            return None
        # Deterministic revenue-by-client routes take precedence.
        if self._is_revenue_by_client_period(intent) or self._is_revenue_by_client_comparison(intent):
            return None
        # Project-scoped cost queries keep their existing routing.
        if looks_like_project_cost_query(blob, subject_area=intent.subject_area):
            return None
        if any(entity.type == "project" for entity in intent.entities):
            return None

        tool, report_type = matched
        # The raw message is the user's literal wording — prefer it for dates.
        date_source = context.conversation.message or intent.specific_intent
        date_from, date_to = resolve_report_date_range(date_source, context.temporal_context)
        tool_input: dict[str, Any] = {"date_from": date_from, "date_to": date_to}
        if report_type:
            tool_input["report_type"] = report_type
        logger.info(
            "[StrategyPlanner] company report guardrail tool=%s report_type=%s range=%s..%s",
            tool,
            report_type,
            date_from,
            date_to,
        )
        step = ExecutionStep(
            step_number=1,
            description=intent.specific_intent or context.conversation.message,
            tool=tool,
            tool_input=tool_input,
            depends_on=[],
            parallel_with=[],
            expected_output=intent.expected_output or "table",
            fallback_if_fails=f"Retry {tool} with the default last 3 months range",
        )
        return Strategy(
            steps=[step],
            synthesis_approach=(
                "Return the financial report directly with a concise executive summary"
            ),
            quality_checks=[
                "Verify numeric values are present in the tool result",
                "Confirm the date range used matches the user's intent",
            ],
            estimated_duration_ms=4000,
        )

    @staticmethod
    def _project_entity_hints(intent: Intent) -> list[str]:
        return [
            entity.value.strip()
            for entity in intent.entities
            if entity.type == "project" and entity.value.strip()
        ]

    @staticmethod
    def _entity_hint_matches_scope(intent: Intent, context: ContextStack) -> bool:
        """Return True when explicit project hints align with session/confirmed project."""
        hints = StrategyPlanner._project_entity_hints(intent)
        if not hints:
            return True

        hint = hints[0].lower()
        names: list[str] = []
        facts = context.working_memory.session_facts
        if facts.get("project_name"):
            names.append(str(facts["project_name"]).lower())
        confirmed = (facts.get("confirmed_entities") or {}).get("project") or {}
        if confirmed.get("name"):
            names.append(str(confirmed["name"]).lower())
        if not names:
            return False

        hint_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", hint)
            if len(token) > 2
        }
        for name in names:
            if hint in name or name in hint:
                return True
            name_tokens = {
                token
                for token in re.findall(r"[a-z0-9]+", name)
                if len(token) > 2
            }
            if hint_tokens and name_tokens and len(hint_tokens & name_tokens) >= 2:
                return True
        return False

    @staticmethod
    def _needs_project_entity_search(intent: Intent, context: ContextStack) -> bool:
        """Route to search_entities when the user names a project that is not in scope."""
        from gateway.core.entity_gate import EntityGate, is_compare_project_intent
        from gateway.core.project_expense_routing import is_project_expense_query

        if is_compare_project_intent(intent) and EntityGate.compare_projects_confirmed(context):
            return False

        hints = StrategyPlanner._project_entity_hints(intent)
        if not hints:
            return False

        blob = f"{intent.specific_intent} {intent.primary_action} {intent.subject_area}"
        expense_like = is_project_expense_query(blob, intent, context) or looks_like_project_cost_query(
            blob,
            subject_area=intent.subject_area,
        )
        if intent.primary_action != "search_entity" and not expense_like:
            return False

        if EntityGate.project_confirmed(context) and StrategyPlanner._entity_hint_matches_scope(
            intent,
            context,
        ):
            return False

        if EntityGate.has_active_project_scope(context):
            return not StrategyPlanner._entity_hint_matches_scope(intent, context)

        return True

    def plan_entity_search(self, intent: Intent, context: ContextStack) -> Strategy:
        """When the user wants to search for entities, not fetch specific project data."""
        del context
        entity_type = "project"
        entity_hint = intent.specific_intent.strip()
        if intent.entities:
            entity_type = intent.entities[0].type or "project"
            entity_hint = intent.entities[0].value.strip() or entity_hint

        step = ExecutionStep(
            step_number=1,
            description=f"Search for {entity_type} matching '{entity_hint}'",
            tool="search_entities",
            tool_input={
                "entity_type": entity_type,
                "query": entity_hint,
                "limit": 10,
                "min_confidence": 0.3,
            },
            depends_on=[],
            parallel_with=[],
            expected_output="entity_list",
            fallback_if_fails="Retry search_entities with broader query terms",
        )
        return Strategy(
            steps=[step],
            synthesis_approach="present_candidates",
            quality_checks=[
                "Verify candidate list reflects search results",
                "Do not fabricate project names or financial numbers",
            ],
            estimated_duration_ms=2000,
        )

    def plan_revenue_comparison(self, intent: Intent, context: ContextStack) -> Strategy:
        """Build a deterministic two-period revenue-by-client comparison."""
        from gateway.core.strategy_fixtures import build_revenue_comparison_strategy

        periods = self._parse_quarter_periods(intent.specific_intent)
        if len(periods) >= 2:
            period_1, period_2 = periods[0], periods[1]
        elif len(periods) == 1:
            period_1 = periods[0]
            year = int(period_1[0][:4]) - 1
            period_2 = (f"{year}-01-01", f"{year}-03-31")
        else:
            period_1 = ("2026-01-01", "2026-03-31")
            period_2 = ("2025-01-01", "2025-03-31")

        limit = self._parse_top_n_limit(intent.specific_intent, default=5)
        return build_revenue_comparison_strategy(
            period_1=period_1,
            period_2=period_2,
            limit=limit,
        )

    def plan_revenue_by_client(self, intent: Intent, context: ContextStack) -> Strategy:
        """Build a deterministic single-period revenue-by-client strategy."""
        from gateway.core.strategy_fixtures import build_revenue_by_client_strategy

        query = intent.specific_intent.lower()
        temporal = context.temporal_context
        if "last quarter" in query:
            date_from, date_to = temporal.last_quarter
        elif "last month" in query:
            date_from, date_to = temporal.last_month
        elif "ytd" in query or "this year" in query:
            date_from, date_to = temporal.ytd
        else:
            date_from, date_to = temporal.last_3_months

        limit = self._parse_top_n_limit(intent.specific_intent, default=10)
        return build_revenue_by_client_strategy(
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    @staticmethod
    def _is_revenue_by_client_period(intent: Intent) -> bool:
        query = intent.specific_intent.lower()
        if intent.primary_action == "compare":
            return False
        has_revenue = any(token in query for token in ("revenue", "sales", "invoice", "turnover"))
        has_client = any(token in query for token in ("client", "customer", "partner"))
        return has_revenue and has_client

    @staticmethod
    def _is_revenue_by_client_comparison(intent: Intent) -> bool:
        query = intent.specific_intent.lower()
        if intent.primary_action != "compare":
            return False
        if intent.subject_area not in {"financial", "revenue", "sales"}:
            if not any(token in query for token in ("revenue", "sales", "invoice")):
                return False
        has_revenue = any(token in query for token in ("revenue", "sales", "invoice", "turnover"))
        has_client = any(token in query for token in ("client", "customer", "partner"))
        has_periods = bool(re.search(r"Q1\s*\d{4}", query, re.IGNORECASE)) or " vs " in query
        return has_revenue and has_client and has_periods

    @staticmethod
    def _parse_quarter_periods(text: str) -> list[tuple[str, str]]:
        periods: list[tuple[str, str]] = []
        for match in re.finditer(r"Q1\s*(\d{4})", text, re.IGNORECASE):
            year = int(match.group(1))
            periods.append((f"{year}-01-01", f"{year}-03-31"))
        return periods

    @staticmethod
    def _parse_top_n_limit(text: str, default: int = 5) -> int:
        match = re.search(r"top\s+(\d+)", text, re.IGNORECASE)
        if match:
            return max(1, min(int(match.group(1)), 20))
        return default

    def plan_simple(self, intent: Intent, context: ContextStack) -> Strategy:
        """Build a single-tool strategy without calling Claude."""
        tool, tool_input = self._resolve_simple_tool(intent, context)
        step = ExecutionStep(
            step_number=1,
            description=intent.specific_intent,
            tool=tool,
            tool_input=tool_input,
            depends_on=[],
            parallel_with=[],
            expected_output=intent.expected_output,
            fallback_if_fails=(
                f"Retry {tool} with default last 3 months date range from temporal context"
            ),
        )
        return Strategy(
            steps=[step],
            synthesis_approach=(
                "Return the single tool result directly with a concise executive summary"
            ),
            quality_checks=[
                "Verify numeric values are present in the tool result",
                "Confirm the date range used matches the user's intent",
            ],
            estimated_duration_ms=3000,
        )

    async def plan_complex(self, intent: Intent, context: ContextStack) -> Strategy:
        """Build a multi-step strategy using Claude."""
        prompt = self._build_complex_prompt(intent, context)
        compact_suffix = (
            "\nIMPORTANT: Return ONLY compact valid JSON. "
            "Keep each description and fallback_if_fails under 80 characters."
        )
        last_error: Exception | None = None

        for attempt in range(2):
            attempt_prompt = prompt if attempt == 0 else prompt + compact_suffix
            try:
                raw_response = await self._client.complete_json(
                    model=self._model,
                    prompt=attempt_prompt,
                    max_tokens=STRATEGY_PLANNER_MAX_TOKENS,
                )
            except Exception as exc:
                raise StrategyException(f"Claude strategy planning failed: {exc}") from exc

            try:
                strategy = self._parse_strategy_response(raw_response)
            except StrategyException as exc:
                last_error = exc
                if attempt == 0:
                    logger.warning(
                        "[StrategyPlanner] Invalid strategy JSON on attempt 1 for intent=%r: %s",
                        intent.specific_intent,
                        exc,
                    )
                    continue
                raise

            if strategy.estimated_duration_ms <= 0:
                raise StrategyException("Strategy estimated_duration_ms must be positive")
            if not strategy.synthesis_approach.strip():
                raise StrategyException("Strategy synthesis_approach must be provided")
            return strategy

        raise StrategyException(
            f"Invalid strategy JSON from Claude after retry: {last_error}",
        ) from last_error

    def _parse_strategy_response(self, raw_response: str) -> Strategy:
        """Parse Claude JSON into Strategy."""
        try:
            payload = json.loads(self._extract_json(raw_response))
            if not isinstance(payload, dict):
                raise ValueError("Strategy JSON must be an object")
            return Strategy.from_dict(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, StrategyException) as exc:
            raise StrategyException(f"Invalid strategy JSON from Claude: {exc}") from exc

    def _validate_intent(self, intent: Intent) -> None:
        """Reject intents that cannot be planned."""
        if not intent.primary_action.strip():
            raise StrategyException("Intent primary_action is required for strategy planning")
        if not intent.subject_area.strip():
            raise StrategyException("Intent subject_area is required for strategy planning")
        if not intent.specific_intent.strip():
            raise StrategyException("Intent specific_intent is required for strategy planning")

    def _single_tool_needed(self, intent: Intent) -> bool:
        """Return True when one gateway tool can fulfill the intent."""
        if intent.estimated_complexity != "simple":
            return False
        if intent.primary_action == "compare":
            return False
        if intent.primary_action == "analyze" and len(intent.entities) > 1:
            return False
        return True

    @staticmethod
    def _is_project_cost_query(intent: Intent, context: ContextStack) -> bool:
        """Return True when a confirmed project expense intelligence query can run."""
        if intent.primary_action == "search_entity":
            return False
        from gateway.core.entity_gate import EntityGate
        from gateway.core.project_expense_routing import is_project_expense_query

        if is_project_expense_query(intent.specific_intent, intent, context):
            facts = context.working_memory.session_facts
            if intent.primary_action == "compare":
                compare_ids = facts.get("compare_project_ids") or facts.get("resolved_project_ids") or []
                return len(compare_ids) >= 2
            if EntityGate.has_active_project_scope(context):
                if StrategyPlanner._project_entity_hints(intent):
                    return StrategyPlanner._entity_hint_matches_scope(intent, context)
                return True
            if extract_project_id_from_text(intent.specific_intent):
                return True
            return False

        if not EntityGate.project_confirmed(context):
            return False
        has_project_entity = any(entity.type == "project" for entity in intent.entities)
        resolved_id = context.working_memory.session_facts.get("resolved_project_id")
        if not has_project_entity and not resolved_id:
            return False
        query = f"{intent.specific_intent} {intent.subject_area}".lower()
        return looks_like_project_cost_query(query) or any(
            token in query for token in ("cost", "costs", "expense", "expenses", "spending")
        )

    @staticmethod
    def _resolve_project_expense_tool_if_applicable(
        intent: Intent,
        context: ContextStack,
    ) -> tuple[str, dict[str, Any]] | None:
        """Route confirmed project expense intelligence queries to E1 tools."""
        from gateway.core.entity_gate import EntityGate
        from gateway.core.project_expense_routing import (
            is_project_expense_query,
            resolve_project_expense_tool_for_strategy,
        )

        if intent.primary_action not in {"fetch_data", "analyze", "compare", "generate_report"}:
            return None
        if not is_project_expense_query(intent.specific_intent, intent, context):
            return None

        if intent.primary_action == "compare":
            try:
                return resolve_project_expense_tool_for_strategy(intent, context)
            except ValueError:
                return None

        if EntityGate.has_active_project_scope(context) or extract_project_id_from_text(intent.specific_intent):
            return resolve_project_expense_tool_for_strategy(intent, context)
        return None

    def _resolve_simple_tool(
        self,
        intent: Intent,
        context: ContextStack,
    ) -> tuple[str, dict[str, Any]]:
        """Map a simple intent to one gateway tool and input payload."""
        query = intent.specific_intent.lower()

        expense_tool = self._resolve_project_expense_tool_if_applicable(intent, context)
        if expense_tool is not None:
            return expense_tool

        if intent.primary_action == "fetch_data" and intent.subject_area == "financial":
            date_source = context.conversation.message or intent.specific_intent
            date_from, date_to = resolve_report_date_range(
                date_source,
                context.temporal_context,
            )
            if any(token in query for token in ("p&l", "profit", "loss", "pandl")):
                return "get_financial_report", {
                    "report_type": "pandl",
                    "date_from": date_from,
                    "date_to": date_to,
                }
            if "balance sheet" in query:
                return "get_financial_report", {
                    "report_type": "balance_sheet",
                    "date_from": date_from,
                    "date_to": date_to,
                }
            if "cash flow" in query:
                return "get_financial_report", {
                    "report_type": "cash_flow",
                    "date_from": date_from,
                    "date_to": date_to,
                }
            if "trial balance" in query:
                return "get_trial_balance", {
                    "date_from": date_from,
                    "date_to": date_to,
                }

        universal = self._resolve_universal_read_tool(intent, context)
        if universal is not None:
            return universal

        if intent.primary_action in {"search_entity", "fetch_data"} and intent.subject_area == "project":
            from gateway.core.entity_gate import EntityGate
            from gateway.core.project_expense_routing import is_project_expense_query

            if is_project_expense_query(intent.specific_intent, intent, context):
                raise StrategyException(
                    "Project expense query requires a confirmed project before expense tools",
                )

            if not EntityGate.project_confirmed(context):
                raise StrategyException(
                    "Project must be confirmed before fetching project financial data",
                )
            return "get_project_expenses", self._build_project_expenses_input(intent, context)

        if intent.primary_action == "search_entity":
            return "search_odoo", {"model": "project.project", "query": intent.specific_intent}

        raise StrategyException(
            f"No simple tool mapping found for intent action={intent.primary_action} "
            f"subject={intent.subject_area}",
        )

    @staticmethod
    def _resolve_universal_read_tool(
        intent: Intent,
        context: ContextStack | None = None,
    ) -> tuple[str, dict[str, Any]] | None:
        """Route open-gate HR/inventory/fleet reads to query_odoo."""
        if intent.primary_action not in {"fetch_data", "search_entity", "analyze"}:
            return None
        if intent.out_of_scope:
            return None

        message = intent.specific_intent
        if context is not None and context.conversation.message:
            message = context.conversation.message

        from gateway.core.hr_query_routing import is_hr_orchestration_query, resolve_hr_tool
        from gateway.core.payroll_query_routing import (
            is_payroll_orchestration_query,
            resolve_payroll_tool,
        )

        if is_payroll_orchestration_query(message, intent, context):
            routed = resolve_payroll_tool(message, intent, context)
            if routed is not None:
                return routed

        if is_hr_orchestration_query(message, intent):
            routed = resolve_hr_tool(message, intent, context)
            if routed is not None:
                return routed

        query = f"{intent.specific_intent} {intent.subject_area}".lower().replace("_", " ")

        if any(token in query for token in ("contract", "agreement")) and "employee" not in query:
            return "query_odoo", {
                "model": "agreement",
                "domain": [],
                "fields": ["name", "code", "partner_id", "amount", "start_date", "end_date", "state"],
                "limit": 50,
                "order": "end_date desc",
            }

        if intent.subject_area == "hr" or any(
            token in query for token in ("employee", "staff", "manager", "payroll")
        ):
            domain: list[Any] = [["active", "=", True]]
            if "manager" in query:
                domain.append(["child_ids", "!=", False])
            if "department" in query or "per department" in query or "grouped" in query:
                return "aggregate_odoo", {
                    "model": "hr.employee",
                    "domain": domain,
                    "group_by": ["department_id"],
                    "aggregates": ["id:count"],
                    "limit": 200,
                }
            if "how many" in query or "count" in query or intent.expected_output == "number":
                return "aggregate_odoo", {
                    "model": "hr.employee",
                    "domain": domain,
                    "group_by": ["department_id"],
                    "aggregates": ["id:count"],
                    "limit": 200,
                }
            if "civil" in query:
                domain.append(["department_id.name", "ilike", "civil"])
            return "query_odoo", {
                "model": "hr.employee",
                "domain": domain,
                "fields": ["name", "job_id", "department_id"],
                "limit": 50,
            }

        if any(
            token in query
            for token in ("purchase order", "purchase orders", " po", "po ", "vendor order")
        ) or (intent.subject_area == "inventory" and "stock" not in query):
            return "query_odoo", {
                "model": "purchase.order",
                "domain": [],
                "fields": ["name", "partner_id", "date_order", "amount_total", "state"],
                "limit": 20,
                "order": "date_order desc",
            }

        if "stock" in query or "inventory" in query:
            return "query_odoo", {
                "model": "stock.quant",
                "domain": [],
                "fields": ["product_id", "quantity", "location_id"],
                "limit": 50,
            }

        if "fleet" in query or "vehicle" in query:
            return "query_odoo", {
                "model": "fleet.vehicle",
                "domain": [],
                "fields": ["name", "license_plate", "model_id", "driver_id"],
                "limit": 50,
            }

        return None

    @staticmethod
    def _build_project_expenses_input(intent: Intent, context: ContextStack) -> dict[str, Any]:
        """Build get_project_expenses input using user-confirmed project IDs only."""
        confirmed = (context.working_memory.session_facts.get("confirmed_entities") or {}).get("project")
        if not confirmed or not confirmed.get("id"):
            raise StrategyException(
                "Project cost query requires a user-confirmed project ID",
            )
        payload: dict[str, Any] = {
            "project_id": int(confirmed["id"]),
        }
        if confirmed.get("name"):
            payload["project_name"] = str(confirmed["name"])
        return payload

    @staticmethod
    def _is_relationship_composition_query(intent: Intent) -> bool:
        """True when the query needs multi-model query_odoo composition."""
        query = f"{intent.specific_intent} {intent.subject_area}".lower().replace("_", " ")
        markers = (
            "no attachment",
            "without attachment",
            "missing attachment",
            "agreement for",
            "contract for",
            "projects for",
            "projects for",
            "attachment type",
            "expiring",
            "without project",
            "per client",
            "wo document",
            "client for",
            "client name for",
        )
        return any(marker in query for marker in markers)

    def _build_complex_prompt(self, intent: Intent, context: ContextStack) -> str:
        """Build a focused Claude prompt for multi-step strategy planning."""
        from gateway.core.project_relationship_context import PROJECT_RELATIONSHIP_PROMPT_SECTION

        entities = [entity.to_dict() for entity in intent.entities]
        return (
            "You are a strategy planner for an ERP assistant.\n"
            f"Intent: {intent.specific_intent}\n"
            f"Primary action: {intent.primary_action}\n"
            f"Subject area: {intent.subject_area}\n"
            f"Entities: {json.dumps(entities, ensure_ascii=True)}\n"
            f"Available tools: {context.capability_manifest.tools_summary()}\n"
            "Return ONLY valid JSON:\n"
            "{"
            '"steps":[{"step_number":1,"description":"...","tool":"tool_name",'
            '"tool_input":{},"depends_on":[],"parallel_with":[],"expected_output":"...",'
            '"fallback_if_fails":"..."}],'
            '"synthesis_approach":"...",'
            '"quality_checks":["..."],'
            '"estimated_duration_ms":3000'
            "}\n"
            "Rules: decompose into atomic steps; set depends_on for sequential steps; "
            "set parallel_with for parallel steps; every step needs fallback_if_fails; "
            "keep total steps under 10; keep descriptions and fallbacks concise.\n"
            "For revenue-by-client period comparisons, use two parallel group_and_aggregate "
            "steps on account.move with group_by=['partner_id'], aggregates=['amount_total:sum'], "
            "date_from/date_to per period — do not chain get_financial_report before group_and_aggregate.\n"
            "For project relationship queries, use 2-4 sequential query_odoo / aggregate_odoo steps. "
            "Never answer with a single project.project text search.\n"
            f"{PROJECT_RELATIONSHIP_PROMPT_SECTION}"
        )

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        """Strip optional markdown fences from Claude output."""
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

"""Intelligent query handler — full 12-stage intelligence pipeline (Phase 9)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from admin.auth.principal import CurrentUser
from gateway.clarify import (
    build_date_range_clarification,
    build_deep_think_date_clarification,
    should_offer_date_clarification,
)
from gateway.core.context_stack import ContextStack
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.conversational_responder import (
    ConversationalResponder,
    NormalModeResponder,
    conversational_suggestions,
    is_conversational_intent,
    is_conversational_message,
    normal_mode_suggestions,
)
from gateway.core.deep_think import is_deep_think_eligible
from gateway.core.entity_gate import (
    ConfirmedEntityRef,
    EntityGate,
    build_entity_near_miss_clarification,
    build_entity_not_found_clarification,
    build_entity_options,
    build_entity_transient_error_clarification,
)
from gateway.core.project_query_utils import is_project_expense_follow_up
from gateway.core.entity_resolver import EntityResolver, OdooProjectSearch, ResolutionStrategy
from gateway.core.execution_orchestrator import ExecutionOrchestrator, ExecutionResult
from gateway.core.failure_handler import Failure, FailureMode, HonestFailureResponder
from gateway.core.gateway_tool_executor import GatewayToolExecutor
from gateway.core.intent_analyzer import EntityReference, Intent, IntentAnalyzer
from gateway.core.interaction_telemetry import InteractionTelemetry
from gateway.core.precompute_cache import GLOBAL_PRECOMPUTE_CACHE, PrecomputeCache
from gateway.core.proactive_intelligence import ProactiveIntelligence
from gateway.core.quality_gate import QualityGate, QualityReview, RetryHandler
from gateway.core.quality_pipeline import (
    QualityResponseReviser,
    build_quality_response,
    quality_gate_log_message,
    tool_results_from_execution,
)
from gateway.core.result_synthesizer import ResultSynthesizer, SynthesizedResult
from gateway.core.smart_suggestions import (
    SmartSuggestionsGenerator,
    remember_shown_suggestions,
)
from gateway.core.strategy_planner import Strategy, StrategyPlanner
from gateway.core.telemetry_capture import TelemetryCapture

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Named stages for logging and honest failure mapping."""

    CACHE = "cache"
    CONTEXT = "context"
    INTENT = "intent"
    OUT_OF_SCOPE = "out_of_scope"
    ENTITY_RESOLUTION = "entity_resolution"
    CLARIFICATION = "clarification"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    SYNTHESIS = "synthesis"
    QUALITY = "quality"
    SUGGESTIONS = "suggestions"
    PROACTIVE = "proactive"
    COMPOSE = "compose"


class PipelineStageError(Exception):
    """Wraps a stage failure for honest user-facing handling."""

    def __init__(self, stage: PipelineStage, cause: Exception) -> None:
        super().__init__(str(cause))
        self.stage = stage
        self.cause = cause


@dataclass
class EntityResolutionMeta:
    """Outcome of entity resolution for one turn."""

    resolved_entities: list[dict[str, Any]] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_matches: list[dict[str, Any]] = field(default_factory=list)
    clarification_options: list[dict[str, Any]] = field(default_factory=list)
    clarification_reason: str = "entity_confirmation"
    not_found: bool = False
    transient_error: bool = False
    query_label: str = ""
    compare_pending_query: str = ""
    compare_resolved_projects: list[dict[str, Any]] = field(default_factory=list)
    weak_matches: bool = False
    entity_near_miss: bool = False
    entity_discovery_count: int = 0
    entity_top_confidence: float = 0.0
    entity_gate_status: str = "skipped"
    entity_confirmed_by_user: bool = False
    entity_auto_confirmed: bool = False
    entity_strategies_used: list[str] = field(default_factory=list)
    entity_strategy_that_matched: str | None = None


@dataclass
class IntelligentQueryResponse:
    """Response from the orchestrated intelligence pipeline."""

    session_id: str
    text: str
    language: str
    visualization: dict[str, Any] | None
    orchestration_log: list[dict[str, Any]]
    execution_duration_ms: int
    orchestration_duration_ms: int
    strategy_step_count: int
    tools_called: list[str]
    execution_result: ExecutionResult | None = None
    suggestions: list[str] = field(default_factory=list)
    quality_pass_rate: float = 1.0
    quality_checks_passed: int = 0
    quality_checks_total: int = 0
    quality_passed: bool = True
    failure_mode: str | None = None
    cache_hit: bool = False
    proactive_cache_keys: list[str] = field(default_factory=list)
    interaction_id: str | None = None
    awaiting_clarification: bool = False
    clarification: dict[str, Any] | None = None
    resolved_entities: list[dict[str, Any]] = field(default_factory=list)
    deep_think_available: bool = False


class _HandlerRequest:
    """Minimal request object for ContextStackBuilder."""

    __slots__ = ("message", "session_id")

    def __init__(self, message: str, session_id: str | None = None) -> None:
        self.message = message
        self.session_id = session_id


class IntelligentQueryHandler:
    """Route queries through the full intelligence pipeline."""

    def __init__(
        self,
        *,
        context_builder: ContextStackBuilder | None = None,
        intent_analyzer: IntentAnalyzer | None = None,
        strategy_planner: StrategyPlanner | None = None,
        synthesizer: ResultSynthesizer | None = None,
        quality_gate: QualityGate | None = None,
        failure_responder: HonestFailureResponder | None = None,
        suggestion_generator: SmartSuggestionsGenerator | None = None,
        proactive_layer: ProactiveIntelligence | None = None,
        precompute_cache: PrecomputeCache | None = None,
        telemetry_capture: TelemetryCapture | None = None,
        entity_resolver: EntityResolver | None = None,
        resolution_strategy: ResolutionStrategy | None = None,
        conversational_responder: ConversationalResponder | None = None,
        normal_mode_responder: NormalModeResponder | None = None,
    ) -> None:
        self._context_builder = context_builder or ContextStackBuilder()
        self._intent_analyzer = intent_analyzer or IntentAnalyzer()
        self._strategy_planner = strategy_planner or StrategyPlanner()
        self._synthesizer = synthesizer or ResultSynthesizer()
        self._quality_gate = quality_gate or QualityGate(
            retry_handler=RetryHandler(reviser=QualityResponseReviser()),
        )
        self._failure_responder = failure_responder or HonestFailureResponder()
        self._suggestion_generator = suggestion_generator or SmartSuggestionsGenerator()
        self._proactive_layer = proactive_layer or ProactiveIntelligence()
        self._precompute_cache = precompute_cache or GLOBAL_PRECOMPUTE_CACHE
        self._telemetry_capture = telemetry_capture
        self._entity_resolver = entity_resolver
        self._resolution_strategy = resolution_strategy or ResolutionStrategy()
        self._conversational_responder = conversational_responder or ConversationalResponder()
        self._normal_mode_responder = normal_mode_responder or NormalModeResponder()

    def _resolve_entity_resolver(self, adapter: Any) -> EntityResolver:
        if self._entity_resolver is not None:
            return self._entity_resolver
        return EntityResolver(OdooProjectSearch(adapter))

    def _resolve_telemetry(self) -> TelemetryCapture:
        if self._telemetry_capture is not None:
            return self._telemetry_capture
        try:
            from admin.db.connection import get_admin_db

            self._telemetry_capture = TelemetryCapture.from_admin_db(get_admin_db())
        except RuntimeError:
            self._telemetry_capture = TelemetryCapture(enabled=False)
        return self._telemetry_capture

    async def handle(
        self,
        message: str,
        user: CurrentUser,
        adapter: Any,
        *,
        session_id: str | None = None,
        language: str = "en",
        skip_clarification: bool = False,
        confirmed_entities: list[ConfirmedEntityRef] | None = None,
        strategy_override: Strategy | None = None,
        executor: Any | None = None,
        deep_think: bool = False,
    ) -> IntelligentQueryResponse:
        """Run the orchestrated intelligence pipeline for one user message."""
        started = time.perf_counter()
        resolved_session = session_id or ""
        telemetry = InteractionTelemetry.start(
            user_id=user.id,
            session_id=resolved_session,
            user_query=message,
            user_query_language=language,
        )
        capture = self._resolve_telemetry()
        context: ContextStack | None = None
        intent: Intent | None = None
        effective_strategy_override = strategy_override
        strategy_used: Strategy | None = strategy_override
        quality_review: QualityReview | None = None
        retries_needed = 0
        entity_meta = EntityResolutionMeta()
        executed_domain: str | None = None

        try:
            await self._run_stage(
                PipelineStage.CACHE,
                capture.apply_follow_up_signals(
                    user_id=user.id,
                    session_id=resolved_session,
                    next_query=message,
                ),
            )

            cached = self._precompute_cache.lookup(resolved_session, message)
            if cached and cached.is_ready():
                return self._finalize_cache_hit(
                    cached=cached,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                )

            request = _HandlerRequest(message=message, session_id=session_id)
            context = await self._run_stage(
                PipelineStage.CONTEXT,
                self._context_builder.build(user, request),
            )

            # Deterministic guardrail: pure greetings/capability questions never
            # reach intent analysis, the strategy planner, or Odoo.
            if is_conversational_message(message):
                return await self._finalize_conversational_response(
                    message=message,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=None,
                )

            intent = await self._run_stage(
                PipelineStage.INTENT,
                self._intent_analyzer.analyze(message, context),
            )

            # LLM-classified conversational turn (general chat, off-topic) — scoped
            # responder instead of tool routing, so it can never raise TOOL_ERROR.
            if is_conversational_intent(intent, message):
                telemetry.intent_extracted = intent
                return await self._finalize_conversational_response(
                    message=message,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

            from gateway.core.project_expense_routing import (
                apply_active_follow_up_context,
                is_followup_to_active,
                select_project_expense_tool,
            )
            from gateway.core.strategy_fixtures import build_single_tool_strategy

            active = context.working_memory.get_active_project()
            is_active_follow_up = is_followup_to_active(message, intent, active)

            if is_active_follow_up:
                logger.info(
                    "[FollowUp] Gating topic-shift — keeping active project %s (id=%s)",
                    active.project_name if active else None,
                    active.project_id if active else None,
                )
            elif context.working_memory.detect_topic_shift(message, intent):
                last_turn = context.working_memory.session_facts.get("last_turn") or {}
                logger.info(
                    "[TopicShift] Detected. Clearing entity context. "
                    "Last: %r, Now: %r",
                    last_turn.get("message"),
                    message,
                )
                self._apply_topic_shift_clear(
                    resolved_session=resolved_session,
                    context=context,
                    user_id=user.id,
                )
            else:
                intent = self._apply_expense_follow_up_intent(message, intent, context)
            from gateway.core.clarification_validation import validate_clarification

            intent = validate_clarification(intent)
            telemetry.intent_extracted = intent

            from gateway.core.project_profile_routing import (
                derive_profile_focus,
                is_project_profile_query,
            )
            from gateway.core.project_records_routing import (
                derive_record_type,
                is_project_records_query,
                records_disqualified,
            )
            from gateway.core.project_activity_routing import (
                derive_activity_type,
                is_project_activity_query,
            )
            from gateway.core.hr_query_routing import (
                is_hr_orchestration_query,
                is_hr_project_staff_query,
                resolve_hr_tool,
            )
            from gateway.core.fleet_query_routing import (
                is_fleet_orchestration_query,
                resolve_fleet_tool,
            )
            from gateway.core.payroll_query_routing import (
                _employee_name_hint,
                is_payroll_file_id_follow_up,
                is_payroll_orchestration_query,
                resolve_payroll_tool,
                should_block_project_entity_search,
            )

            has_active_project = bool(active and active.project_id)
            hr_project_staff_query = is_hr_project_staff_query(message)
            payroll_orchestration_query = is_payroll_orchestration_query(message, intent, context)
            fleet_orchestration_query = is_fleet_orchestration_query(message, intent)
            if resolve_fleet_tool(message, intent, context) is not None:
                fleet_orchestration_query = True
            from gateway.core.project_expense_routing import is_project_expense_query

            project_expense_query = is_project_expense_query(message, intent, context)
            if resolve_payroll_tool(message, intent, context) is not None:
                payroll_orchestration_query = True
            if "payslip" in message.lower() or "salary slip" in message.lower():
                payroll_orchestration_query = True
            record_type = derive_record_type(message)
            activity_type = derive_activity_type(message)
            # Records lane fires on explicit "<type> of/for <project>" phrasing
            # OR when a record-type keyword appears in a follow-up to an active
            # project (e.g. the "Show <project> purchase orders" chip, where the
            # type trails the project name). Records take precedence over the
            # profile lane: an explicit record-type keyword (invoices, PO,
            # timesheets, staff, ...) must not be swallowed by an LLM
            # "project_attribute"/"hr" classification.
            records_query = (
                record_type is not None
                and not records_disqualified(message)
                and (
                    is_project_records_query(message, intent)
                    or is_active_follow_up
                    or has_active_project
                )
            )
            activity_query = (
                not records_query
                and activity_type is not None
                and not records_disqualified(message)
                and (
                    is_project_activity_query(message, intent)
                    or is_active_follow_up
                    or has_active_project
                )
            )
            hr_orchestration_query = is_hr_orchestration_query(message, intent)
            profile_query = (
                not records_query
                and not activity_query
                and not hr_project_staff_query
                and not hr_orchestration_query
                and not payroll_orchestration_query
                and not fleet_orchestration_query
                and is_project_profile_query(message, intent)
            )

            # Project profile/record/activity/payroll/HR lanes are served by direct ORM reads —
            # an LLM "out of scope" verdict must not pre-empt them.
            if (
                intent.out_of_scope
                and not profile_query
                and not records_query
                and not activity_query
                and not payroll_orchestration_query
                and not hr_orchestration_query
                and not fleet_orchestration_query
            ):
                return self._finalize_failure(
                    failure=self._failure_responder.failure_from_intent(intent, message),
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

            if profile_query and not records_query and not activity_query:
                profile_intent = self._prepare_profile_intent(message, intent, context)
                if profile_intent is None:
                    if intent.subject_area == "project_attribute":
                        return self._finalize_project_attribute_response(
                            message=message,
                            context=context,
                            telemetry=telemetry,
                            resolved_session=resolved_session,
                            language=language,
                            started=started,
                            intent=intent,
                        )
                    profile_query = False
                else:
                    intent = profile_intent

            if records_query:
                records_intent = self._prepare_records_intent(message, intent, context)
                if records_intent is None:
                    # No project reference anywhere — let the normal pipeline
                    # handle it (global record queries are not this lane).
                    records_query = False
                else:
                    intent = records_intent

            if activity_query:
                activity_intent = self._prepare_activity_intent(message, intent, context)
                if activity_intent is None:
                    activity_query = False
                else:
                    intent = activity_intent

            intent = EntityGate.infer_entity_hints(message, intent)

            from gateway.core.project_query_utils import (
                extract_broad_project_search_term,
                is_broad_project_search,
            )

            if (
                effective_strategy_override is None
                and (
                    payroll_orchestration_query
                    or is_payroll_file_id_follow_up(message, context)
                )
            ):
                early_payroll = resolve_payroll_tool(message, intent, context)
                if early_payroll is not None:
                    early_tool, early_input = early_payroll
                    from dataclasses import replace

                    intent = replace(
                        intent,
                        primary_action="fetch_data",
                        subject_area="payroll",
                        specific_intent=message,
                        requires_clarification=False,
                        clarification_question=None,
                    )
                    effective_strategy_override = build_single_tool_strategy(
                        tool=early_tool,
                        tool_input=early_input,
                        description=f"Payroll query: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info(
                        "[PayrollRouting] Early force %s for %r",
                        early_tool,
                        message[:80],
                    )

            if payroll_orchestration_query and _employee_name_hint(message):
                from gateway.core.hr_payroll_composer import (
                    classify_payroll_subtype,
                    extract_employee_name,
                    get_pending_hr_context,
                    parse_period_window,
                )

                existing = get_pending_hr_context(context)
                is_payroll_follow_up = existing.get("domain") == "payroll"
                prior_query = (
                    str(existing.get("prior_query") or message)
                    if is_payroll_follow_up
                    else message
                )
                resolved = dict(existing.get("resolved") or {})
                period = parse_period_window(message, context)
                if period:
                    resolved["date_from"] = period.date_from
                    resolved["date_to"] = period.date_to
                    resolved["label"] = period.label
                name_hint = extract_employee_name(message)
                if name_hint:
                    resolved["employee_name_hint"] = name_hint

                pending_ctx = {
                    "query": prior_query,
                    "payroll_context": True,
                    "options": [],
                }
                context.working_memory.session_facts["pending_entity_clarification"] = pending_ctx
                context.working_memory.session_facts["pending_hr_context"] = {
                    "domain": "payroll",
                    "subtype": classify_payroll_subtype(prior_query),
                    "prior_query": prior_query,
                    "awaiting": existing.get("awaiting", []) if is_payroll_follow_up else [],
                    "resolved": resolved,
                }

            broad_search_query = is_broad_project_search(message)
            if broad_search_query and should_block_project_entity_search(message, context):
                broad_search_query = False
            if broad_search_query and effective_strategy_override is None:
                search_term = extract_broad_project_search_term(message) or message.strip()
                effective_strategy_override = build_single_tool_strategy(
                    tool="search_entities",
                    tool_input={
                        "entity_type": "project",
                        "query": search_term,
                        "limit": 20,
                        "min_confidence": 0.3,
                    },
                    description=f"Search projects matching: {search_term}",
                    expected_output="entity_list",
                )
                logger.info(
                    "[BroadSearch] Forcing search_entities query=%r",
                    search_term,
                )

            # Normal mode (Deep Think OFF): the AI prepares the answer itself —
            # interprets, narrows scope, and offers Deep Think for actual figures.
            # Predefined Odoo methods only run when deep_think is active.
            # Follow-ups to an active Deep Think project keep their tool flow.
            # Project profile queries bypass this: header reads need no Deep Think.
            if (
                not deep_think
                and not profile_query
                and not records_query
                and not activity_query
                and not broad_search_query
                and not hr_orchestration_query
                and not payroll_orchestration_query
                and not project_expense_query
                and not is_active_follow_up
                and effective_strategy_override is None
                and self._requires_deep_think(message, intent)
            ):
                return await self._finalize_normal_mode_response(
                    message=message,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                    skip_clarification=skip_clarification,
                )

            if is_active_follow_up and active is not None:
                logger.info(
                    "[FollowUp] Using active project %s (id=%s) — skipping entity resolution",
                    active.project_name,
                    active.project_id,
                )
                apply_active_follow_up_context(context, active)
                intent = self._apply_expense_follow_up_intent(message, intent, context)
                entity_meta = EntityResolutionMeta(
                    entity_gate_status="skipped",
                    resolved_entities=[
                        {
                            "entity_type": "project",
                            "project_id": active.project_id,
                            "project_name": active.project_name,
                            "id": active.project_id,
                            "name": active.project_name,
                        },
                    ],
                )
                if profile_query:
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_profile",
                        tool_input={
                            "project_id": active.project_id,
                            "focus": derive_profile_focus(message),
                        },
                        description=f"Profile follow-up: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info(
                        "[FollowUp] Forcing get_project_profile with project_id=%s",
                        active.project_id,
                    )
                elif records_query:
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_records",
                        tool_input={
                            "project_id": active.project_id,
                            "record_type": derive_record_type(message) or "invoices",
                        },
                        description=f"Records follow-up: {message}",
                        expected_output=intent.expected_output or "table",
                    )
                    logger.info(
                        "[FollowUp] Forcing get_project_records with project_id=%s",
                        active.project_id,
                    )
                elif activity_query:
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_activity",
                        tool_input={
                            "project_id": active.project_id,
                            "activity_type": derive_activity_type(message) or "progress",
                            "language": language,
                        },
                        description=f"Activity follow-up: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info(
                        "[FollowUp] Forcing get_project_activity with project_id=%s",
                        active.project_id,
                    )
                else:
                    forced = select_project_expense_tool(message, intent, context)
                    if forced:
                        tool_name, tool_input = forced
                        tool_input = {
                            **tool_input,
                            "project_id": active.project_id,
                            "project_name": active.project_name,
                        }
                        effective_strategy_override = build_single_tool_strategy(
                            tool=tool_name,
                            tool_input=tool_input,
                            description=f"Follow-up: {message}",
                            expected_output=intent.expected_output or "table",
                        )
                        logger.info(
                            "[FollowUp] Forcing tool %s with project_id=%s",
                            tool_name,
                            active.project_id,
                        )
            else:
                intent, entity_meta = await self._run_stage(
                    PipelineStage.ENTITY_RESOLUTION,
                    self._run_entity_gate(
                        intent,
                        context,
                        adapter,
                        message,
                        confirmed_entities=confirmed_entities,
                    ),
                )
            telemetry.intent_extracted = intent

            if entity_meta.resolved_entities and resolved_session:
                from gateway.session_scope import SessionScopeStore

                scope_update: dict[str, Any] = {}
                for item in entity_meta.resolved_entities:
                    if item.get("entity_type") == "project" or item.get("project_id"):
                        scope_update["project_id"] = int(item.get("project_id") or item.get("id"))
                        scope_update["project_name"] = item.get("project_name") or item.get("name")
                    if item.get("entity_type") == "partner" or item.get("partner_id"):
                        scope_update["partner_ids"] = [int(item.get("partner_id") or item.get("id"))]
                        scope_update["client_name"] = item.get("partner_name") or item.get("name")
                if scope_update:
                    SessionScopeStore.update(resolved_session, **scope_update)
                confirmed = context.working_memory.session_facts.get("confirmed_entities") or {}
                if confirmed:
                    SessionScopeStore.update(resolved_session, confirmed_entities=confirmed)

            if entity_meta.needs_clarification:
                self._apply_entity_telemetry(telemetry, entity_meta)
                return self._finalize_entity_clarification(
                    entity_meta=entity_meta,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    message=message,
                    started=started,
                    intent=intent,
                    profile_query=profile_query or records_query or activity_query,
                )

            clarification = self._check_clarification_needed(
                message=message,
                intent=intent,
                context=context,
                language=language,
                skip_clarification=skip_clarification,
            )
            if clarification is not None:
                return self._finalize_clarification(
                    clarification=clarification,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

            if profile_query and effective_strategy_override is None:
                profile_project_id = self._resolved_project_id(context, entity_meta)
                if profile_project_id is not None:
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_profile",
                        tool_input={
                            "project_id": profile_project_id,
                            "focus": derive_profile_focus(message),
                        },
                        description=f"Project profile: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info(
                        "[ProjectProfile] Forcing get_project_profile project_id=%s focus=%s",
                        profile_project_id,
                        derive_profile_focus(message),
                    )

            if records_query and effective_strategy_override is None:
                records_project_id = self._resolved_project_id(context, entity_meta)
                if records_project_id is not None:
                    record_type = derive_record_type(message) or "invoices"
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_records",
                        tool_input={
                            "project_id": records_project_id,
                            "record_type": record_type,
                        },
                        description=f"Project records: {message}",
                        expected_output=intent.expected_output or "table",
                    )
                    logger.info(
                        "[ProjectRecords] Forcing get_project_records project_id=%s type=%s",
                        records_project_id,
                        record_type,
                    )

            if activity_query and effective_strategy_override is None:
                activity_project_id = self._resolved_project_id(context, entity_meta)
                if activity_project_id is not None:
                    act_type = derive_activity_type(message) or "progress"
                    effective_strategy_override = build_single_tool_strategy(
                        tool="get_project_activity",
                        tool_input={
                            "project_id": activity_project_id,
                            "activity_type": act_type,
                            "language": language,
                        },
                        description=f"Project activity: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info(
                        "[ProjectActivity] Forcing get_project_activity project_id=%s type=%s",
                        activity_project_id,
                        act_type,
                    )

            if hr_project_staff_query and effective_strategy_override is None:
                hr_project_id = self._resolved_project_id(context, entity_meta)
                if hr_project_id is not None:
                    routed = resolve_hr_tool(message, intent, context)
                    if routed is not None:
                        tool_name, tool_input = routed
                        effective_strategy_override = build_single_tool_strategy(
                            tool=tool_name,
                            tool_input=tool_input,
                            description=f"HR project staff: {message}",
                            expected_output=intent.expected_output or "table",
                        )
                        logger.info(
                            "[HRProjectStaff] Forcing %s project_id=%s",
                            tool_name,
                            hr_project_id,
                        )

            if (
                effective_strategy_override is None
                and payroll_orchestration_query
                and not profile_query
                and not records_query
                and not activity_query
            ):
                routed = resolve_payroll_tool(message, intent, context)
                if routed is not None:
                    tool_name, tool_input = routed
                    effective_strategy_override = build_single_tool_strategy(
                        tool=tool_name,
                        tool_input=tool_input,
                        description=f"Payroll query: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info("[PayrollRouting] Forcing %s for %r", tool_name, message[:80])

            if (
                effective_strategy_override is None
                and fleet_orchestration_query
                and not profile_query
                and not records_query
                and not activity_query
            ):
                routed = resolve_fleet_tool(message, intent, context)
                if routed is not None:
                    tool_name, tool_input = routed
                    effective_strategy_override = build_single_tool_strategy(
                        tool=tool_name,
                        tool_input=tool_input,
                        description=f"Fleet query: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info("[FleetRouting] Forcing %s for %r", tool_name, message[:80])

            if (
                effective_strategy_override is None
                and hr_orchestration_query
                and not profile_query
                and not records_query
                and not activity_query
            ):
                routed = resolve_hr_tool(message, intent, context)
                if routed is not None:
                    tool_name, tool_input = routed
                    effective_strategy_override = build_single_tool_strategy(
                        tool=tool_name,
                        tool_input=tool_input,
                        description=f"HR query: {message}",
                        expected_output=intent.expected_output or "summary",
                    )
                    logger.info("[HRRouting] Forcing %s for %r", tool_name, message[:80])

            pipeline = await self._run_pipeline_orchestration(
                message=message,
                adapter=adapter,
                context=context,
                intent=intent,
                language=language,
                session_id=session_id,
                strategy_override=effective_strategy_override,
                executor=executor,
                current_user=user,
            )
            self._persist_execution_scope(
                resolved_session=resolved_session,
                context=context,
                execution_result=pipeline["execution_result"],
            )
            self._persist_hr_payroll_scope(
                context=context,
                execution_result=pipeline["execution_result"],
                message=message,
            )
            self._persist_hr_request_scope(
                context=context,
                execution_result=pipeline["execution_result"],
                message=message,
            )
            self._persist_fleet_scope(
                context=context,
                execution_result=pipeline["execution_result"],
                message=message,
            )
            strategy_used = pipeline["strategy"]
            quality_review = pipeline["quality_review"]
            retries_needed = pipeline["retries_needed"]

            synthesized = pipeline["synthesized"]
            proactive_cache_keys: list[str] = []
            suggestions: list[str] = []

            hr_disambiguation = self._hr_employee_disambiguation_from_pipeline(
                pipeline.get("tool_results") or [],
                message=message,
                context=context,
                language=language,
            )
            if hr_disambiguation is not None:
                hr_context = hr_disambiguation.get("hr_context")
                if isinstance(hr_context, dict):
                    context.working_memory.session_facts["pending_hr_context"] = dict(hr_context)
                duration_ms = int((time.perf_counter() - started) * 1000)
                return self._finalize_clarification(
                    clarification=hr_disambiguation,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

            try:
                proactive = await self._run_stage(
                    PipelineStage.PROACTIVE,
                    self._proactive_layer.anticipate(synthesized, intent, context),
                )
                suggestions = await self._run_stage_optional(
                    PipelineStage.SUGGESTIONS,
                    self._generate_suggestions_from_proactive(
                        synthesized=synthesized,
                        intent=intent,
                        context=context,
                        pipeline=pipeline,
                        language=language,
                        proactive=proactive,
                    ),
                    fallback=[],
                )
                proactive = self._proactive_layer.schedule_precompute(
                    proactive,
                    session_id=resolved_session,
                    runner=self._build_precompute_runner(
                        user=user,
                        adapter=adapter,
                        language=language,
                        session_id=session_id,
                    ),
                )
                proactive_cache_keys = proactive.scheduled_cache_keys
            except Exception as exc:
                logger.warning("[IntelligentQueryHandler] proactive/suggestions stage skipped: %s", exc)

            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "[IntelligentQueryHandler] query=%r steps=%d duration_ms=%d tools=%s quality=%s suggestions=%d proactive=%d",
                message[:80],
                pipeline["strategy_step_count"],
                duration_ms,
                pipeline["tools_called"],
                quality_gate_log_message(quality_review),
                len(suggestions),
                len(proactive_cache_keys),
            )

            response = IntelligentQueryResponse(
                session_id=resolved_session,
                text=pipeline["text"],
                language=language,
                visualization=pipeline["visualization"],
                orchestration_log=pipeline["orchestration_log"],
                execution_duration_ms=duration_ms,
                orchestration_duration_ms=pipeline["orchestration_duration_ms"],
                strategy_step_count=pipeline["strategy_step_count"],
                tools_called=pipeline["tools_called"],
                execution_result=pipeline["execution_result"],
                suggestions=suggestions,
                quality_pass_rate=quality_review.pass_rate if quality_review else 1.0,
                quality_checks_passed=pipeline["quality_checks_passed"],
                quality_checks_total=pipeline["quality_checks_total"],
                quality_passed=quality_review.passed if quality_review else True,
                proactive_cache_keys=proactive_cache_keys,
                interaction_id=telemetry.interaction_id,
                resolved_entities=entity_meta.resolved_entities,
            )
            self._apply_entity_telemetry(telemetry, entity_meta)
            from gateway.core.topic_shift import infer_turn_domain

            executed_domain = infer_turn_domain(
                pipeline["tools_called"],
                pipeline.get("tool_results"),
            )
            telemetry.finalize_response(
                response_text=response.text,
                visualization=response.visualization,
                suggestions=response.suggestions,
                total_duration_ms=duration_ms,
                orchestration_duration_ms=pipeline["orchestration_duration_ms"],
                proactive_cache_keys=response.proactive_cache_keys,
                quality_review=quality_review,
                quality_checks_passed=pipeline["quality_checks_passed"],
                quality_checks_total=pipeline["quality_checks_total"],
                retries_needed=retries_needed,
                tools_called=pipeline["tools_called"],
                orchestration_log=pipeline["orchestration_log"],
                intent=intent,
                strategy=strategy_used,
            )
            return response
        except PipelineStageError as exc:
            failure = HonestFailureResponder.failure_from_stage(
                exc.stage.value,
                exc.cause,
                message,
            )
            if failure is None:
                logger.warning(
                    "[IntelligentQueryHandler] entity_resolution stage returned no failure; "
                    "expected clarification flow",
                )
                if context is None:
                    context = self._minimal_context(user, message, session_id)
                return self._finalize_clarification(
                    clarification={
                        "reason": "entity_confirmation",
                        "question": "Please confirm which record you mean.",
                        "options": [],
                    },
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )
            if context is None:
                context = self._minimal_context(user, message, session_id)
            return self._finalize_failure(
                failure=failure,
                context=context,
                telemetry=telemetry,
                resolved_session=resolved_session,
                language=language,
                started=started,
                intent=intent,
            )
        except Exception as exc:
            logger.exception("[IntelligentQueryHandler] unexpected pipeline error")
            failure = HonestFailureResponder.failure_from_stage(
                PipelineStage.COMPOSE.value,
                exc,
                message,
            )
            if context is None:
                context = self._minimal_context(user, message, session_id)
            return self._finalize_failure(
                failure=failure,
                context=context,
                telemetry=telemetry,
                resolved_session=resolved_session,
                language=language,
                started=started,
                intent=intent,
            )
        finally:
            if intent is not None and resolved_session:
                from gateway.core.topic_shift import infer_turn_domain, persist_last_turn

                persist_last_turn(resolved_session, message, intent, domain=executed_domain)
            await capture.record(telemetry)

    @staticmethod
    def _apply_topic_shift_clear(
        *,
        resolved_session: str,
        context: ContextStack,
        user_id: int,
    ) -> None:
        """Clear stale entity scope and user-scoped tool cache after a topic shift."""
        from gateway.core.topic_shift import apply_topic_shift_clear
        from gateway.tool_cache import ToolResultCache

        if resolved_session:
            apply_topic_shift_clear(resolved_session, context.working_memory)
        ToolResultCache.clear_user(user_id)

    async def _run_pipeline_orchestration(
        self,
        *,
        message: str,
        adapter: Any,
        context: ContextStack,
        intent: Intent,
        language: str,
        session_id: str | None,
        strategy_override: Strategy | None,
        executor: Any | None,
        current_user: CurrentUser | None = None,
    ) -> dict[str, Any]:
        strategy = strategy_override
        if strategy is None:
            strategy = await self._run_stage(
                PipelineStage.STRATEGY,
                self._strategy_planner.plan(intent, context),
            )

        execution_result = await self._run_stage(
            PipelineStage.EXECUTION,
            self._execute_strategy(
                strategy=strategy,
                context=context,
                adapter=adapter,
                message=message,
                session_id=session_id,
                executor=executor,
                current_user=current_user,
            ),
        )

        synthesized = await self._run_stage(
            PipelineStage.SYNTHESIS,
            self._synthesize_results(execution_result, intent),
        )

        pipeline_core = self._build_pipeline_payload(
            message=message,
            intent=intent,
            context=context,
            language=language,
            strategy=strategy,
            execution_result=execution_result,
            synthesized=synthesized,
        )

        final_response, quality_review, retries_needed = await self._run_stage(
            PipelineStage.QUALITY,
            self._quality_gate.ensure_quality(
                pipeline_core["quality_response"],
                intent,
                context,
            ),
        )
        logger.info("[QualityGate] %s", quality_gate_log_message(quality_review))

        pipeline_core.update(
            {
                "text": final_response.text,
                "visualization": final_response.visualization,
                "synthesized": SynthesizedResult(
                    text=final_response.text,
                    visualization=final_response.visualization,
                ),
                "quality_review": quality_review,
                "retries_needed": retries_needed,
                "quality_checks_passed": sum(
                    1 for check in quality_review.checks if check.passed
                ),
                "quality_checks_total": len(quality_review.checks),
            },
        )
        return pipeline_core

    async def _execute_strategy(
        self,
        *,
        strategy: Strategy,
        context: ContextStack,
        adapter: Any,
        message: str,
        session_id: str | None,
        executor: Any | None,
        current_user: CurrentUser | None = None,
    ) -> ExecutionResult:
        tool_executor = executor or GatewayToolExecutor(
            adapter,
            session_id=session_id,
            user_message=message,
            user=current_user,
        )
        orchestrator = ExecutionOrchestrator(tool_executor, retry_delay_seconds=0.5)
        return await orchestrator.execute(strategy, context)

    async def _synthesize_results(
        self,
        execution_result: ExecutionResult,
        intent: Intent,
    ) -> SynthesizedResult:
        return self._synthesizer.synthesize(execution_result, intent)

    def _build_pipeline_payload(
        self,
        *,
        message: str,
        intent: Intent,
        context: ContextStack,
        language: str,
        strategy: Strategy,
        execution_result: ExecutionResult,
        synthesized: SynthesizedResult,
    ) -> dict[str, Any]:
        orchestration_log = [entry.to_dict() for entry in execution_result.orchestration_log]
        tools_called = [entry.tool for entry in execution_result.orchestration_log]
        orchestration_duration_ms = sum(entry.duration_ms for entry in execution_result.orchestration_log)
        tool_results = tool_results_from_execution(execution_result.results)

        quality_response = build_quality_response(
            message=message,
            text=synthesized.text,
            visualization=synthesized.visualization,
            tool_names=tools_called,
            tool_results=tool_results,
            language=language,
            intent=intent,
            context=context,
        )
        return {
            "quality_response": quality_response,
            "text": synthesized.text,
            "visualization": synthesized.visualization,
            "synthesized": synthesized,
            "orchestration_log": orchestration_log,
            "tools_called": tools_called,
            "orchestration_duration_ms": orchestration_duration_ms,
            "strategy_step_count": len(strategy.steps),
            "strategy": strategy,
            "execution_result": execution_result,
            "tool_results": tool_results,
        }

    async def _generate_suggestions_from_proactive(
        self,
        *,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
        pipeline: dict[str, Any],
        language: str,
        proactive: Any,
    ) -> list[str]:
        suggestions = self._suggestion_generator.generate(
            synthesized,
            intent,
            context,
            tool_names=pipeline["tools_called"],
            tool_results=pipeline["tool_results"],
            language=language,
            predicted_actions=proactive.predicted_actions,
        )
        remember_shown_suggestions(context, suggestions)
        return suggestions

    @staticmethod
    def _apply_expense_follow_up_intent(
        message: str,
        intent: Intent,
        context: ContextStack,
    ) -> Intent:
        """Clear spurious clarification when user drills into the active project."""
        logger.info(
            "[TRACE apply_followup] intent.entities BEFORE=%s",
            [(entity.type, entity.value) for entity in intent.entities],
        )
        if not is_project_expense_follow_up(message):
            logger.info(
                "[TRACE apply_followup] intent.entities AFTER=%s",
                [(entity.type, entity.value) for entity in intent.entities],
            )
            return intent
        if not EntityGate.has_active_project_scope(context):
            logger.info(
                "[TRACE apply_followup] intent.entities AFTER=%s",
                [(entity.type, entity.value) for entity in intent.entities],
            )
            return intent
        updates: dict[str, Any] = {
            "requires_clarification": False,
            "clarification_question": None,
        }
        if intent.subject_area in {"general", "other", "financial"}:
            updates["subject_area"] = "project"
        if intent.primary_action in {"other", "ask_question", "search_entity"}:
            updates["primary_action"] = "analyze"
        updated = replace(intent, **updates)
        logger.info(
            "[TRACE apply_followup] intent.entities AFTER=%s",
            [(entity.type, entity.value) for entity in updated.entities],
        )
        return updated

    @staticmethod
    def _persist_execution_scope(
        *,
        resolved_session: str,
        context: ContextStack,
        execution_result: ExecutionResult,
    ) -> None:
        """Persist project scope from tool results for follow-up turns."""
        if not resolved_session:
            return
        from gateway.session_entities import update_scope_from_tool_result

        for step in execution_result.strategy_used.steps:
            result = execution_result.results.get(step.step_number)
            if result is None:
                continue
            update_scope_from_tool_result(
                resolved_session,
                step.tool,
                step.tool_input or {},
                result,
            )
            if not isinstance(result, dict) or result.get("status") != "success":
                continue
            project_id = result.get("project_id") or (step.tool_input or {}).get("project_id")
            if not project_id:
                continue
            pid = int(project_id)
            project_name = result.get("project_name")
            if step.tool in {
                "get_project_expense_summary",
                "get_project_expense_breakdown",
                "get_project_expenses",
            }:
                context.working_memory.set_active_project(
                    pid,
                    str(project_name or f"Project {pid}"),
                    confirmed=True,
                )
            if step.tool == "get_project_expense_summary":
                context.working_memory.session_facts["last_expense_summary_project_id"] = pid

    @staticmethod
    def _persist_hr_payroll_scope(
        *,
        context: ContextStack,
        execution_result: ExecutionResult,
        message: str,
    ) -> None:
        """Keep employee, period, and subtype in session for payslip drill-downs."""
        from gateway.core.hr_payroll_composer import (
            classify_payroll_subtype,
            parse_period_window,
            resolve_payroll_subtype,
        )

        for step in execution_result.strategy_used.steps:
            result = execution_result.results.get(step.step_number)
            if not isinstance(result, dict) or result.get("_source") != "get_payslip_detail":
                continue
            if result.get("note") and not result.get("payslip"):
                continue
            pending = dict(context.working_memory.session_facts.get("pending_hr_context") or {})
            resolved = dict(pending.get("resolved") or {})
            if result.get("employee_file_id"):
                resolved["employee_file_id"] = str(result["employee_file_id"])
            if result.get("employee_name"):
                resolved["employee_name_hint"] = str(result["employee_name"])
            period = parse_period_window(message, context)
            if period:
                resolved["date_from"] = period.date_from
                resolved["date_to"] = period.date_to
                resolved["label"] = period.label
            elif resolved.get("date_from"):
                pass
            payslip = result.get("payslip") or {}
            if payslip.get("date_from") and payslip.get("date_to") and not resolved.get("date_from"):
                resolved["date_from"] = str(payslip["date_from"])
                resolved["date_to"] = str(payslip["date_to"])
            subtype = resolve_payroll_subtype(message, context)
            if subtype == "payslip_header":
                subtype = classify_payroll_subtype(message) or "payslip_header"
            pending.update(
                {
                    "domain": "payroll",
                    "subtype": subtype,
                    "prior_query": pending.get("prior_query") or message,
                    "awaiting": [],
                    "resolved": resolved,
                }
            )
            context.working_memory.session_facts["pending_hr_context"] = pending
            return

    @staticmethod
    def _persist_hr_request_scope(
        *,
        context: ContextStack,
        execution_result: ExecutionResult,
        message: str,
    ) -> None:
        """Keep employee and recent request ids in session for HR request drill-downs."""
        for step in execution_result.strategy_used.steps:
            result = execution_result.results.get(step.step_number)
            if not isinstance(result, dict):
                continue
            source = str(result.get("_source") or "")
            if source not in {"list_employee_requests", "get_employee_request_detail"}:
                continue
            if source == "list_employee_requests" and not result.get("requests") and not result.get("note"):
                continue
            pending = dict(context.working_memory.session_facts.get("pending_hr_context") or {})
            resolved = dict(pending.get("resolved") or {})
            if result.get("employee_file_id"):
                resolved["employee_file_id"] = str(result["employee_file_id"])
            if result.get("employee_name"):
                resolved["employee_name_hint"] = str(result["employee_name"])
            if source == "list_employee_requests":
                recent_ids = result.get("recent_request_ids") or [
                    row.get("id") for row in (result.get("requests") or [])[:5] if isinstance(row, dict)
                ]
                if recent_ids:
                    resolved["recent_request_ids"] = recent_ids
            if source == "get_employee_request_detail" and result.get("request_id"):
                resolved["recent_request_ids"] = [result.get("request_id")]
            pending.update(
                {
                    "domain": "hr",
                    "subtype": "hr_request_detail" if source == "get_employee_request_detail" else "hr_request_list",
                    "prior_query": pending.get("prior_query") or message,
                    "awaiting": [],
                    "resolved": resolved,
                }
            )
            context.working_memory.session_facts["pending_hr_context"] = pending
            return

    @staticmethod
    def _persist_fleet_scope(
        *,
        context: ContextStack,
        execution_result: ExecutionResult,
        message: str,
    ) -> None:
        """Keep employee scope for fleet follow-ups."""
        for step in execution_result.strategy_used.steps:
            result = execution_result.results.get(step.step_number)
            if not isinstance(result, dict) or result.get("_source") != "search_fleet_vehicles":
                continue
            pending = dict(context.working_memory.session_facts.get("pending_hr_context") or {})
            resolved = dict(pending.get("resolved") or {})
            if result.get("employee_file_id"):
                resolved["employee_file_id"] = str(result["employee_file_id"])
            if result.get("employee_name"):
                resolved["employee_name_hint"] = str(result["employee_name"])
            pending.update(
                {
                    "domain": "fleet",
                    "subtype": "fleet_search",
                    "prior_query": pending.get("prior_query") or message,
                    "awaiting": [],
                    "resolved": resolved,
                }
            )
            context.working_memory.session_facts["pending_hr_context"] = pending
            return

    @staticmethod
    def _normalize_clarify_query(text: str) -> str:
        import re

        return re.sub(r"[^\w\s]", " ", (text or "").lower()).strip()

    @classmethod
    def _queries_equivalent_for_clarification(cls, left: str, right: str) -> bool:
        normalized_left = cls._normalize_clarify_query(left)
        normalized_right = cls._normalize_clarify_query(right)
        if not normalized_left or not normalized_right:
            return False
        if normalized_left == normalized_right:
            return True
        if normalized_left in normalized_right or normalized_right in normalized_left:
            return True
        left_tokens = set(normalized_left.split())
        right_tokens = set(normalized_right.split())
        shared = left_tokens & right_tokens
        return len(shared) >= 2 and len(shared) >= min(len(left_tokens), len(right_tokens)) // 2

    @staticmethod
    def _try_repeat_query_entity_confirm(
        message: str,
        context: ContextStack,
        confirmed_entities: list[ConfirmedEntityRef] | None,
    ) -> list[ConfirmedEntityRef] | None:
        """When the user re-sends the same query, apply the prior default clarification option."""
        if confirmed_entities:
            return confirmed_entities
        pending = context.working_memory.session_facts.get("pending_entity_clarification")
        if not isinstance(pending, dict):
            return None
        prior_query = str(pending.get("query") or "").strip()
        if not IntelligentQueryHandler._queries_equivalent_for_clarification(prior_query, message):
            return None
        options = pending.get("options") or []
        defaults = [option for option in options if option.get("is_default")]
        chosen = defaults[0] if len(defaults) == 1 else (options[0] if len(options) == 1 else None)
        if chosen is None:
            return None
        if chosen.get("action") != "confirm_entity" or not chosen.get("entity_id"):
            return None
        return [
            ConfirmedEntityRef(
                type=str(chosen.get("entity_type") or "project"),
                id=int(chosen["entity_id"]),
                name=str(chosen.get("label") or chosen["entity_id"]),
            ),
        ]

    async def _run_entity_gate(
        self,
        intent: Intent,
        context: ContextStack,
        adapter: Any,
        message: str,
        *,
        confirmed_entities: list[ConfirmedEntityRef] | None = None,
    ) -> tuple[Intent, EntityResolutionMeta]:
        meta = EntityResolutionMeta()
        if not EntityGate.intent_requires_entity_confirmation(message, intent, context):
            meta.entity_gate_status = "skipped"
            if confirmed_entities:
                confirmed_map: dict[str, dict[str, Any]] = {}
                for item in confirmed_entities:
                    confirmed_map[item.type] = {"id": item.id, "name": item.name}
                    meta.resolved_entities.append(
                        {
                            "entity_type": item.type,
                            "id": item.id,
                            "name": item.name,
                            "project_id": item.id if item.type == "project" else None,
                            "project_name": item.name if item.type == "project" else None,
                            "action": "user_confirmed",
                        },
                    )
                EntityGate.apply_confirmed_entities(context, confirmed_map)
            return intent, meta

        confirmed_entities = self._try_repeat_query_entity_confirm(
            message,
            context,
            confirmed_entities,
        )
        gate = EntityGate(adapter, project_resolver=self._resolve_entity_resolver(adapter))
        result = await gate.evaluate(intent, context, message, confirmed_entities)
        meta.entity_discovery_count = result.entity_discovery_count
        meta.entity_top_confidence = result.entity_top_confidence
        meta.entity_strategies_used = list(result.entity_strategies_used)
        meta.entity_strategy_that_matched = result.entity_strategy_that_matched
        meta.entity_gate_status = result.status

        if result.status == "not_required":
            meta.entity_gate_status = "skipped"
            return intent, meta

        if result.status == "confirmed":
            context.working_memory.session_facts.pop("pending_entity_clarification", None)
            meta.entity_confirmed_by_user = bool(confirmed_entities)
            meta.entity_auto_confirmed = not bool(confirmed_entities)
            if result.compare_project_ids:
                EntityGate.apply_compare_projects(
                    context,
                    result.compare_resolved_projects,
                    result.compare_project_ids,
                )
                for proj in result.compare_resolved_projects:
                    meta.resolved_entities.append(
                        {
                            "entity_type": "project",
                            "id": proj.get("id"),
                            "name": proj.get("name"),
                            "project_id": proj.get("id"),
                            "project_name": proj.get("name"),
                            "action": "auto_confirmed" if not confirmed_entities else "user_confirmed",
                        },
                    )
                if intent.requires_clarification:
                    intent = replace(
                        intent,
                        requires_clarification=False,
                        clarification_question=None,
                    )
                return intent, meta

            EntityGate.apply_confirmed_entities(context, result.confirmed)
            updated_entities: list[EntityReference] = []
            for entity in intent.entities:
                confirmed = result.confirmed.get(entity.type)
                if confirmed:
                    updated_entities.append(
                        EntityReference(
                            type=entity.type,
                            value=str(confirmed.get("name") or entity.value),
                            confidence=1.0,
                        ),
                    )
                else:
                    updated_entities.append(entity)
            confirm_action = "user_confirmed" if confirmed_entities else "auto_confirmed"
            for entity_type, confirmed in result.confirmed.items():
                meta.resolved_entities.append(
                    {
                        "entity_type": entity_type,
                        "id": confirmed.get("id"),
                        "name": confirmed.get("name"),
                        "project_id": confirmed.get("id") if entity_type == "project" else None,
                        "project_name": confirmed.get("name") if entity_type == "project" else None,
                        "partner_id": confirmed.get("id") if entity_type == "partner" else None,
                        "partner_name": confirmed.get("name") if entity_type == "partner" else None,
                        "action": confirm_action,
                    },
                )
            return replace(intent, entities=updated_entities or intent.entities), meta

        if result.status == "not_found":
            meta.needs_clarification = True
            meta.not_found = True
            meta.query_label = result.query_label
            return intent, meta

        if result.status == "transient_error":
            meta.needs_clarification = True
            meta.transient_error = True
            meta.query_label = result.query_label
            return intent, meta

        meta.needs_clarification = True
        meta.weak_matches = result.status == "weak_confirmation"
        meta.entity_near_miss = result.entity_near_miss
        if result.entity_near_miss:
            meta.clarification_reason = "entity_near_miss"
        meta.clarification_matches = result.matches
        meta.clarification_options = result.options or build_entity_options(result.matches)
        meta.query_label = result.query_label
        from gateway.core.payroll_query_routing import is_payroll_orchestration_query

        context.working_memory.session_facts["pending_entity_clarification"] = {
            "query": message,
            "options": meta.clarification_options,
            "payroll_context": is_payroll_orchestration_query(message, intent, context),
        }
        meta.compare_pending_query = result.compare_pending_query
        meta.compare_resolved_projects = list(result.compare_resolved_projects)
        if result.compare_pending_query:
            context.working_memory.session_facts["compare_pending_query"] = result.compare_pending_query
            context.working_memory.session_facts["compare_resolved_projects"] = list(
                result.compare_resolved_projects,
            )
        if intent.requires_clarification:
            intent = replace(
                intent,
                requires_clarification=False,
                clarification_question=None,
            )
        return intent, meta

    @staticmethod
    def _apply_entity_telemetry(telemetry: InteractionTelemetry, meta: EntityResolutionMeta) -> None:
        telemetry.entity_discovery_count = meta.entity_discovery_count
        telemetry.entity_top_confidence = meta.entity_top_confidence
        telemetry.entity_gate_status = meta.entity_gate_status
        telemetry.entity_confirmed_by_user = meta.entity_confirmed_by_user
        telemetry.entity_auto_confirmed = meta.entity_auto_confirmed
        telemetry.entity_strategies_used = list(meta.entity_strategies_used)
        telemetry.entity_strategy_that_matched = meta.entity_strategy_that_matched

    @staticmethod
    def _ensure_project_entities(message: str, intent: Intent) -> Intent:
        """Backward-compatible wrapper — prefer EntityGate.infer_entity_hints."""
        return EntityGate.infer_entity_hints(message, intent)

    def _check_clarification_needed(
        self,
        *,
        message: str,
        intent: Intent,
        context: ContextStack,
        language: str,
        skip_clarification: bool,
    ) -> dict[str, Any] | None:
        if skip_clarification:
            return None

        if intent.requires_clarification and intent.clarification_question:
            return {
                "reason": "intent_clarification",
                "question": intent.clarification_question,
                "question_ar": intent.clarification_question,
            }

        if should_offer_date_clarification(message):
            from gateway.core.payroll_query_routing import (
                is_payroll_orchestration_query,
                message_has_payroll_period,
            )

            if is_payroll_orchestration_query(message, intent, context) and message_has_payroll_period(
                message,
            ):
                return None
            return build_date_range_clarification(language)

        return None

    @staticmethod
    async def _run_stage(stage: PipelineStage, awaitable: Any) -> Any:
        try:
            return await awaitable
        except PipelineStageError:
            raise
        except Exception as exc:
            raise PipelineStageError(stage, exc) from exc

    @staticmethod
    async def _run_stage_optional(stage: PipelineStage, awaitable: Any, *, fallback: Any) -> Any:
        try:
            return await awaitable
        except Exception as exc:
            logger.warning("[IntelligentQueryHandler] optional stage %s failed: %s", stage.value, exc)
            return fallback

    def _finalize_cache_hit(
        self,
        *,
        cached: Any,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
    ) -> IntelligentQueryResponse:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[IntelligentQueryHandler] precompute cache hit session=%s key=%s",
            resolved_session[:8],
            cached.key,
        )
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=cached.text,
            language=language,
            visualization=cached.visualization,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            execution_result=None,
            suggestions=cached.suggestions,
            cache_hit=True,
            proactive_cache_keys=[cached.key],
            interaction_id=telemetry.interaction_id,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=response.visualization,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            cache_hit=True,
            proactive_cache_keys=response.proactive_cache_keys,
        )
        return response

    @staticmethod
    def _requires_deep_think(message: str, intent: Intent) -> bool:
        """True when the query asks for real ERP data (Deep Think territory)."""
        data_action = intent.primary_action in (
            "fetch_data",
            "analyze",
            "compare",
            "generate_report",
            "search_entity",
        )
        data_subject = intent.subject_area in (
            "financial",
            "project",
            "sales",
            "inventory",
            "hr",
        )
        if data_action and data_subject:
            return True
        return is_deep_think_eligible(message)

    @staticmethod
    def _build_report_date_clarification(
        *,
        message: str,
        context: ContextStack,
        language: str,
    ) -> dict[str, Any] | None:
        """Clickable period card for company-wide report queries (normal mode).

        Selecting any option resumes the query with Deep Think so the real
        Odoo figures are fetched in one click — no typing, no manual toggle.
        """
        from gateway.core.strategy_planner import match_company_report

        if match_company_report(message) is None:
            return None
        return build_deep_think_date_clarification(
            message,
            context.temporal_context,
            language,
        )

    async def _finalize_normal_mode_response(
        self,
        *,
        message: str,
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
        intent: Intent,
        skip_clarification: bool,
    ) -> IntelligentQueryResponse:
        """AI-prepared answer for data queries when Deep Think is off — no Odoo."""
        if not skip_clarification:
            report_clarification = self._build_report_date_clarification(
                message=message,
                context=context,
                language=language,
            )
            if report_clarification is not None:
                return self._finalize_clarification(
                    clarification=report_clarification,
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

        clarification = self._check_clarification_needed(
            message=message,
            intent=intent,
            context=context,
            language=language,
            skip_clarification=skip_clarification,
        )
        if clarification is not None:
            return self._finalize_clarification(
                clarification=clarification,
                context=context,
                telemetry=telemetry,
                resolved_session=resolved_session,
                language=language,
                started=started,
                intent=intent,
            )

        text = await self._normal_mode_responder.respond(
            message,
            context,
            intent,
            language=language,
        )
        suggestions = normal_mode_suggestions(message, context, language)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[IntelligentQueryHandler] normal-mode (no Deep Think) turn message=%r "
            "duration_ms=%d",
            message[:80],
            duration_ms,
        )
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=text,
            language=language,
            visualization=None,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            execution_result=None,
            suggestions=suggestions[:3],
            interaction_id=telemetry.interaction_id,
            deep_think_available=True,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            intent=intent,
        )
        return response

    async def _finalize_conversational_response(
        self,
        *,
        message: str,
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
        intent: Intent | None,
    ) -> IntelligentQueryResponse:
        """Scoped conversational reply — no tools, no Odoo, no strategy planning."""
        text = await self._conversational_responder.respond(
            message,
            context,
            language=language,
        )
        suggestions = conversational_suggestions(language)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[IntelligentQueryHandler] conversational turn message=%r duration_ms=%d",
            message[:80],
            duration_ms,
        )
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=text,
            language=language,
            visualization=None,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            execution_result=None,
            suggestions=suggestions[:3],
            interaction_id=telemetry.interaction_id,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            intent=intent,
        )
        return response

    @staticmethod
    def _prepare_profile_intent(
        message: str,
        intent: Intent,
        context: ContextStack,
    ) -> Intent | None:
        """Reclassify a profile intent for the profile lane.

        Returns None when no project reference exists anywhere (message hint,
        intent entities, active project) — caller keeps the honest deferral.
        """
        if intent.out_of_scope:
            return None

        from gateway.core.project_query_utils import extract_project_name_hint

        hint = extract_project_name_hint(message)
        if hint:
            # Strip leading trade/amount qualifiers ("civil amount of <X>") — the
            # LLM often grabs the trade word as the project name.
            entities = [e for e in intent.entities if e.type != "project"]
            entities.append(EntityReference(type="project", value=hint, confidence=0.9))
            has_project = True
        else:
            entities = list(intent.entities)
            has_project = any(entity.type == "project" for entity in entities)
        if not has_project:
            active = context.working_memory.get_active_project()
            if not (active and active.project_id):
                return None
        return replace(
            intent,
            subject_area="project",
            primary_action="fetch_data",
            entities=entities,
            out_of_scope=False,
            requires_clarification=False,
            clarification_question=None,
        )

    @staticmethod
    def _prepare_records_intent(
        message: str,
        intent: Intent,
        context: ContextStack,
    ) -> Intent | None:
        """Steer a record-list query into the records lane.

        Returns None when no project reference exists anywhere (message hint,
        intent entities, active project) — the caller falls back to the
        normal pipeline.
        """
        from gateway.core.project_records_routing import extract_records_project_hint

        hint = extract_records_project_hint(message)
        if hint:
            # The stripped hint ("invoices of <X>" -> "<X>") is more reliable
            # than the LLM entity, which often grabs the record keyword itself
            # (e.g. project="petty cash"). Replace any project entities with it.
            entities = [e for e in intent.entities if e.type != "project"]
            entities.append(EntityReference(type="project", value=hint, confidence=0.9))
            has_project = True
        else:
            entities = list(intent.entities)
            has_project = any(entity.type == "project" for entity in entities)
        if not has_project:
            active = context.working_memory.get_active_project()
            if not (active and active.project_id):
                return None
        return replace(
            intent,
            subject_area="project",
            primary_action="fetch_data",
            entities=entities,
            out_of_scope=False,
            requires_clarification=False,
            clarification_question=None,
        )

    @staticmethod
    def _prepare_activity_intent(
        message: str,
        intent: Intent,
        context: ContextStack,
    ) -> Intent | None:
        """Steer an activity query into the activity lane."""
        from gateway.core.project_activity_routing import extract_activity_project_hint

        hint = extract_activity_project_hint(message)
        if hint:
            entities = [e for e in intent.entities if e.type != "project"]
            entities.append(EntityReference(type="project", value=hint, confidence=0.9))
            has_project = True
        else:
            entities = list(intent.entities)
            has_project = any(entity.type == "project" for entity in entities)
        if not has_project:
            active = context.working_memory.get_active_project()
            if not (active and active.project_id):
                return None
        return replace(
            intent,
            subject_area="project",
            primary_action="fetch_data",
            entities=entities,
            out_of_scope=False,
            requires_clarification=False,
            clarification_question=None,
        )

    @staticmethod
    def _resolved_project_id(
        context: ContextStack,
        entity_meta: EntityResolutionMeta,
    ) -> int | None:
        """Project id confirmed this turn or active in session, if any."""
        for item in entity_meta.resolved_entities:
            pid = item.get("project_id") or (
                item.get("id") if item.get("entity_type") == "project" else None
            )
            if pid:
                return int(pid)
        facts = context.working_memory.session_facts
        confirmed = (facts.get("confirmed_entities") or {}).get("project") or {}
        if confirmed.get("id"):
            return int(confirmed["id"])
        if facts.get("resolved_project_id"):
            return int(facts["resolved_project_id"])
        active = context.working_memory.get_active_project()
        if active and active.project_id:
            return int(active.project_id)
        return None

    def _finalize_project_attribute_response(
        self,
        *,
        message: str,
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
        intent: Intent,
    ) -> IntelligentQueryResponse:
        from gateway.core.project_attribute_utils import build_project_attribute_response_text
        from gateway.core.project_query_utils import extract_project_name_hint

        active = context.working_memory.get_active_project()
        project_ref = (
            active.project_name
            if active and active.project_name
            else extract_project_name_hint(message) or "that project"
        )
        text = build_project_attribute_response_text(project_ref)
        suggestions = [
            f"Show me {project_ref} expenses",
            f"Break down {project_ref} by account",
        ]
        duration_ms = int((time.perf_counter() - started) * 1000)
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=text,
            language=language,
            visualization=None,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            execution_result=None,
            suggestions=suggestions[:3],
            interaction_id=telemetry.interaction_id,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            intent=intent,
        )
        return response

    def _finalize_failure(
        self,
        *,
        failure: Failure,
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
        intent: Intent | None,
    ) -> IntelligentQueryResponse:
        failure_response = self._failure_responder.respond(failure, context)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[HonestFailureResponder] mode=%s stage=%s",
            failure_response.failure_mode.value,
            failure.details.get("stage"),
        )
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=failure_response.text,
            language=language,
            visualization=None,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            execution_result=None,
            suggestions=failure_response.suggestions[:3],
            failure_mode=failure_response.failure_mode.value,
            interaction_id=telemetry.interaction_id,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            failure_mode=response.failure_mode,
            intent=intent,
        )
        return response

    def _hr_employee_disambiguation_from_pipeline(
        self,
        tool_results: list[Any],
        *,
        message: str,
        context: ContextStack,
        language: str,
    ) -> dict[str, Any] | None:
        """Return structured clarification when HR tools find multiple employee matches."""
        from gateway.core.hr_clarification import build_employee_disambiguation_clarification
        from gateway.core.hr_payroll_composer import (
            get_pending_hr_context,
            parse_period_window,
            resolve_payroll_subtype,
        )

        for payload in reversed(tool_results):
            if not isinstance(payload, dict):
                continue
            ambiguous = payload.get("ambiguous_employees") or []
            if not ambiguous:
                continue
            pending = get_pending_hr_context(context)
            prior_query = str(pending.get("prior_query") or message)
            source = str(payload.get("_source") or "")
            domain = pending.get("domain") or (
                "payroll" if source == "get_payslip_detail" else "hr"
            )
            subtype = resolve_payroll_subtype(prior_query, context)
            if subtype == "payslip_header":
                subtype = resolve_payroll_subtype(message, context)
            name_hint = str(payload.get("employee_name") or "").strip()
            query_label = name_hint or prior_query
            clarification = build_employee_disambiguation_clarification(
                query=prior_query,
                employees=ambiguous,
                domain=str(domain),
                subtype=subtype,
                language=language,
            )
            if name_hint and name_hint.lower() not in prior_query.lower():
                clarification["question"] = (
                    f"I found multiple employees matching **{name_hint}**.\n\n"
                    "Which employee do you mean? Pick a name below or reply with their File ID."
                )
            resolved = dict(pending.get("resolved") or {})
            period = parse_period_window(message, context) or parse_period_window(prior_query, context)
            if period:
                resolved["date_from"] = period.date_from
                resolved["date_to"] = period.date_to
                resolved["label"] = period.label
            hr_context = dict(clarification.get("hr_context") or {})
            hr_context["resolved"] = resolved
            hr_context["subtype"] = subtype
            clarification["hr_context"] = hr_context
            return clarification
        return None

    def _finalize_clarification(
        self,
        *,
        clarification: dict[str, Any],
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        started: float,
        intent: Intent | None,
    ) -> IntelligentQueryResponse:
        prompt = (
            clarification.get("question_ar")
            if language == "ar"
            else clarification.get("question")
        ) or clarification.get("question", "")
        hr_context = clarification.get("hr_context")
        if isinstance(hr_context, dict):
            context.working_memory.session_facts["pending_hr_context"] = dict(hr_context)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response = IntelligentQueryResponse(
            session_id=resolved_session,
            text=str(prompt),
            language=language,
            visualization=None,
            orchestration_log=[],
            execution_duration_ms=duration_ms,
            orchestration_duration_ms=0,
            strategy_step_count=0,
            tools_called=[],
            suggestions=[],
            awaiting_clarification=True,
            clarification=clarification,
            interaction_id=telemetry.interaction_id,
        )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=[],
            total_duration_ms=duration_ms,
            intent=intent,
        )
        return response

    def _finalize_entity_clarification(
        self,
        *,
        entity_meta: EntityResolutionMeta,
        context: ContextStack,
        telemetry: InteractionTelemetry,
        resolved_session: str,
        language: str,
        message: str,
        started: float,
        intent: Intent | None,
        profile_query: bool = False,
    ) -> IntelligentQueryResponse:
        # Profile questions are not financial — don't promise "financial data".
        if profile_query:
            generic_question = (
                "Please confirm which project you mean."
                if language != "ar"
                else "يرجى تأكيد المشروع المقصود."
            )
        else:
            from gateway.core.payroll_query_routing import is_payroll_orchestration_query

            pending = context.working_memory.session_facts.get("pending_entity_clarification") or {}
            payroll_context = bool(pending.get("payroll_context"))
            if payroll_context or (
                intent is not None and is_payroll_orchestration_query(message, intent, context)
            ):
                generic_question = (
                    "Please confirm which record you mean before I fetch payroll data."
                    if language != "ar"
                    else "يرجى تأكيد السجل المطلوب قبل جلب بيانات الرواتب."
                )
            else:
                generic_question = (
                    "Please confirm which record you mean before I fetch financial data."
                    if language != "ar"
                    else "يرجى تأكيد السجل المطلوب قبل جلب البيانات المالية."
                )
        has_candidates = bool(entity_meta.clarification_options)
        if has_candidates:
            duration_ms = int((time.perf_counter() - started) * 1000)
            if entity_meta.entity_near_miss:
                query_label = entity_meta.query_label or message
                near_miss = build_entity_near_miss_clarification(
                    query_label,
                    entity_meta.clarification_options,
                    language=language,
                )
                question = near_miss["question"]
                clarification = {
                    "reason": "entity_near_miss",
                    "question": question,
                    "matches": entity_meta.clarification_matches,
                    "options": entity_meta.clarification_options,
                }
            elif entity_meta.compare_pending_query:
                pending = entity_meta.compare_pending_query
                resolved = entity_meta.compare_resolved_projects
                if resolved:
                    resolved_label = ", ".join(
                        str(item.get("name") or item.get("id")) for item in resolved
                    )
                    question = (
                        f"I've matched **{resolved_label}**. "
                        f"Which project did you mean for **{pending}**?"
                        if language != "ar"
                        else f"طابقت **{resolved_label}**. أي مشروع تقصد لـ **{pending}**؟"
                    )
                elif len(entity_meta.clarification_options) == 1:
                    label = entity_meta.clarification_options[0].get("label", "")
                    question = (
                        f"Compare including **{label}** — is this the project you mean for **{pending}**?"
                        if language != "ar"
                        else f"مقارنة تتضمن **{label}** — هل هذا المشروع المقصود لـ **{pending}**؟"
                    )
                else:
                    question = (
                        f"Which project did you mean for **{pending}**?"
                        if language != "ar"
                        else f"أي مشروع تقصد لـ **{pending}**؟"
                    )
                clarification = {
                    "reason": "compare_entity_confirmation",
                    "question": question,
                    "matches": entity_meta.clarification_matches,
                    "options": entity_meta.clarification_options,
                    "compare_pending_query": pending,
                }
                if entity_meta.compare_resolved_projects:
                    clarification["compare_resolved"] = entity_meta.compare_resolved_projects
            elif entity_meta.weak_matches:
                if len(entity_meta.clarification_options) == 1:
                    label = entity_meta.clarification_options[0].get("label", "")
                    question = (
                        f"I found a possible match: **{label}**. Is this the one?"
                        if language != "ar"
                        else f"وجدت تطابقاً محتملاً: **{label}**. هل هذا المقصود؟"
                    )
                else:
                    question = (
                        "These are possible matches but I'm not confident. Did you mean one of these?"
                        if language != "ar"
                        else "هذه نتائج محتملة لكن الثقة منخفضة. هل تقصد أحد هذه؟"
                    )
                clarification = {
                    "reason": "entity_confirmation",
                    "question": question,
                    "matches": entity_meta.clarification_matches,
                    "options": entity_meta.clarification_options,
                }
            elif len(entity_meta.clarification_options) == 1:
                label = entity_meta.clarification_options[0].get("label", "")
                from gateway.core.hr_query_routing import is_hr_person_query
                from gateway.core.payroll_query_routing import is_payroll_orchestration_query

                if profile_query:
                    question = (
                        f"I found **{label}**. Is this the project you mean?"
                        if language != "ar"
                        else f"هل تقصد **{label}**؟"
                    )
                elif intent is not None and (
                    is_payroll_orchestration_query(message, intent, context)
                    or is_hr_person_query(message)
                ):
                    question = (
                        f"I found **{label}**. Is this the employee you mean?"
                        if language != "ar"
                        else f"هل تقصد الموظف **{label}**؟"
                    )
                else:
                    question = (
                        f"I found **{label}**. Is this the one you want financial data for?"
                        if language != "ar"
                        else f"هل تقصد **{label}**؟"
                    )
                clarification = {
                    "reason": "entity_confirmation",
                    "question": question,
                    "matches": entity_meta.clarification_matches,
                    "options": entity_meta.clarification_options,
                }
            else:
                question = generic_question
                clarification = {
                    "reason": "entity_confirmation",
                    "question": question,
                    "matches": entity_meta.clarification_matches,
                    "options": entity_meta.clarification_options,
                }
            response = IntelligentQueryResponse(
                session_id=resolved_session,
                text=question,
                language=language,
                visualization=None,
                orchestration_log=[],
                execution_duration_ms=duration_ms,
                orchestration_duration_ms=0,
                strategy_step_count=0,
                tools_called=[],
                suggestions=[],
                failure_mode=None,
                awaiting_clarification=True,
                clarification=clarification,
                interaction_id=telemetry.interaction_id,
            )
        elif entity_meta.not_found:
            query = entity_meta.query_label or message
            clarification = build_entity_not_found_clarification(query, language=language)
            duration_ms = int((time.perf_counter() - started) * 1000)
            response = IntelligentQueryResponse(
                session_id=resolved_session,
                text=clarification["question"],
                language=language,
                visualization=None,
                orchestration_log=[],
                execution_duration_ms=duration_ms,
                orchestration_duration_ms=0,
                strategy_step_count=0,
                tools_called=[],
                suggestions=[
                    f"Show all projects containing {query.split()[0] if query.split() else query}",
                    "Search by Work Order number",
                ],
                failure_mode=FailureMode.NO_DATA_FOUND.value,
                awaiting_clarification=True,
                clarification=clarification,
                interaction_id=telemetry.interaction_id,
            )
        elif entity_meta.transient_error:
            clarification = build_entity_transient_error_clarification(language=language)
            duration_ms = int((time.perf_counter() - started) * 1000)
            response = IntelligentQueryResponse(
                session_id=resolved_session,
                text=clarification["question"],
                language=language,
                visualization=None,
                orchestration_log=[],
                execution_duration_ms=duration_ms,
                orchestration_duration_ms=0,
                strategy_step_count=0,
                tools_called=[],
                suggestions=[],
                failure_mode=FailureMode.SERVICE_UNAVAILABLE.value,
                awaiting_clarification=True,
                clarification=clarification,
                interaction_id=telemetry.interaction_id,
            )
        else:
            duration_ms = int((time.perf_counter() - started) * 1000)
            question = generic_question
            clarification = {
                "reason": "entity_confirmation",
                "question": question,
                "matches": entity_meta.clarification_matches,
                "options": entity_meta.clarification_options,
            }
            response = IntelligentQueryResponse(
                session_id=resolved_session,
                text=question,
                language=language,
                visualization=None,
                orchestration_log=[],
                execution_duration_ms=duration_ms,
                orchestration_duration_ms=0,
                strategy_step_count=0,
                tools_called=[],
                suggestions=[],
                failure_mode=None,
                awaiting_clarification=True,
                clarification=clarification,
                interaction_id=telemetry.interaction_id,
            )
        telemetry.finalize_response(
            response_text=response.text,
            visualization=None,
            suggestions=response.suggestions,
            total_duration_ms=duration_ms,
            failure_mode=response.failure_mode,
            intent=intent,
        )
        return response

    @staticmethod
    def _minimal_context(
        user: CurrentUser,
        message: str,
        session_id: str | None,
    ) -> ContextStack:
        from gateway.core.business_context import BusinessContext
        from gateway.core.capability_manifest import CAPABILITY_MANIFEST
        from gateway.core.context_stack import ConversationContext, QualityTargets
        from gateway.core.temporal_context import TemporalContext
        from gateway.core.user_context import UserContext
        from gateway.core.working_memory import WorkingMemory

        from datetime import datetime, timezone

        return ContextStack(
            user=UserContext(
                user_id=user.id,
                name=user.name,
                file_id=user.file_id,
                primary_role=user.roles[0] if user.roles else "user",
                level=100 if user.is_super_admin else 30,
                permissions=set(user.permissions),
                primary_department=user.department_codes[0] if user.department_codes else "",
                departments=list(user.department_codes),
                preferred_language=user.language,
                preferred_currency="AED",
                default_date_range="last_3_months",
                response_style="brief",
                last_login=datetime.now(timezone.utc),
                typical_queries=[],
            ),
            conversation=ConversationContext(session_id=session_id, message=message),
            capability_manifest=CAPABILITY_MANIFEST,
            working_memory=WorkingMemory(),
            business_context=BusinessContext(),
            temporal_context=TemporalContext.build(),
            quality_targets=QualityTargets(),
        )

    async def _run_orchestration(
        self,
        *,
        message: str,
        user: CurrentUser,
        adapter: Any,
        context: Any,
        intent: Intent,
        language: str,
        session_id: str | None,
        strategy_override: Strategy | None,
        executor: Any | None,
    ) -> dict[str, Any]:
        """Backward-compatible orchestration helper for precompute runner."""
        return await self._run_pipeline_orchestration(
            message=message,
            adapter=adapter,
            context=context,
            intent=intent,
            language=language,
            session_id=session_id,
            strategy_override=strategy_override,
            executor=executor,
            current_user=user,
        )

    def _build_precompute_runner(
        self,
        *,
        user: CurrentUser,
        adapter: Any,
        language: str,
        session_id: str | None,
    ):
        cache = self._precompute_cache
        handler = self

        async def _runner(
            *,
            session_id: str,
            cache_key: str,
            query_message: str,
            suggestion_text: str,
        ) -> None:
            del suggestion_text
            try:
                request = _HandlerRequest(message=query_message, session_id=session_id)
                context = await handler._context_builder.build(user, request)
                intent = await handler._intent_analyzer.analyze(query_message, context)
                if intent.out_of_scope:
                    cache.mark_failed(session_id, cache_key, "Predicted query is out of scope")
                    return

                intent = EntityGate.infer_entity_hints(query_message, intent)
                intent, entity_meta = await handler._run_entity_gate(
                    intent,
                    context,
                    adapter,
                    query_message,
                )
                if entity_meta.needs_clarification:
                    cache.mark_failed(session_id, cache_key, "Predicted query needs entity confirmation")
                    return
                if entity_meta.resolved_entities:
                    EntityGate.apply_confirmed_entities(
                        context,
                        context.working_memory.session_facts.get("confirmed_entities") or {},
                    )
                pipeline = await handler._run_orchestration(
                    message=query_message,
                    user=user,
                    adapter=adapter,
                    context=context,
                    intent=intent,
                    language=language,
                    session_id=session_id,
                    strategy_override=None,
                    executor=None,
                )
                suggestions = handler._suggestion_generator.generate(
                    pipeline["synthesized"],
                    intent,
                    context,
                    tool_names=pipeline["tools_called"],
                    tool_results=pipeline["tool_results"],
                    language=language,
                    predicted_actions=[],
                )[:3]
                cache.put_ready(
                    session_id,
                    cache_key,
                    text=pipeline["text"],
                    visualization=pipeline["visualization"],
                    suggestions=suggestions,
                )
            except Exception as exc:
                logger.warning(
                    "[ProactiveIntelligence] precompute failed key=%s error=%s",
                    cache_key,
                    exc,
                )
                cache.mark_failed(session_id, cache_key, str(exc))

        return _runner

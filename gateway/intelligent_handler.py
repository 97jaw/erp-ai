"""Intelligent query handler — full 12-stage intelligence pipeline (Phase 9)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from admin.auth.principal import CurrentUser
from gateway.clarify import build_date_range_clarification, should_offer_date_clarification
from gateway.core.context_stack import ContextStack
from gateway.core.context_stack_builder import ContextStackBuilder
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

            intent = await self._run_stage(
                PipelineStage.INTENT,
                self._intent_analyzer.analyze(message, context),
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

            if intent.out_of_scope:
                return self._finalize_failure(
                    failure=self._failure_responder.failure_from_intent(intent, message),
                    context=context,
                    telemetry=telemetry,
                    resolved_session=resolved_session,
                    language=language,
                    started=started,
                    intent=intent,
                )

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

            intent = EntityGate.infer_entity_hints(message, intent)

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

            pipeline = await self._run_pipeline_orchestration(
                message=message,
                adapter=adapter,
                context=context,
                intent=intent,
                language=language,
                session_id=session_id,
                strategy_override=effective_strategy_override,
                executor=executor,
            )
            self._persist_execution_scope(
                resolved_session=resolved_session,
                context=context,
                execution_result=pipeline["execution_result"],
            )
            strategy_used = pipeline["strategy"]
            quality_review = pipeline["quality_review"]
            retries_needed = pipeline["retries_needed"]

            synthesized = pipeline["synthesized"]
            proactive_cache_keys: list[str] = []
            suggestions: list[str] = []
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
                from gateway.core.topic_shift import persist_last_turn

                persist_last_turn(resolved_session, message, intent)
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
    ) -> ExecutionResult:
        tool_executor = executor or GatewayToolExecutor(
            adapter,
            session_id=session_id,
            user_message=message,
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
        prior_query = str(pending.get("query") or "").strip().lower()
        if prior_query != message.strip().lower():
            return None
        options = pending.get("options") or []
        defaults = [option for option in options if option.get("is_default")]
        if len(defaults) != 1:
            return None
        option = defaults[0]
        if option.get("action") != "confirm_entity" or not option.get("entity_id"):
            return None
        return [
            ConfirmedEntityRef(
                type=str(option.get("entity_type") or "project"),
                id=int(option["entity_id"]),
                name=str(option.get("label") or option["entity_id"]),
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
        context.working_memory.session_facts["pending_entity_clarification"] = {
            "query": message,
            "options": meta.clarification_options,
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
    ) -> IntelligentQueryResponse:
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
                question = (
                    "Please confirm which record you mean before I fetch financial data."
                    if language != "ar"
                    else "يرجى تأكيد السجل المطلوب قبل جلب البيانات المالية."
                )
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
            question = (
                "Please confirm which record you mean before I fetch financial data."
                if language != "ar"
                else "يرجى تأكيد السجل المطلوب قبل جلب البيانات المالية."
            )
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

"""Integration tests for the full IntelligentQueryHandler pipeline (Phase 9)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace
from typing import Any

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.context_stack import ContextStack, ConversationContext
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.entity_gate import ConfirmedEntityRef
from gateway.core.entity_resolver import EntityResolver
from gateway.core.failure_handler import contains_fabricated_excuse
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.proactive_intelligence import ProactiveActions, ProactiveIntelligence
from gateway.core.result_synthesizer import ResultSynthesizer, SynthesizedResult
from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
from gateway.core.strategy_planner import ExecutionStep, Strategy
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.core.working_memory import WorkingMemory
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG
from tests.core.test_execution_orchestrator import MockToolExecutor


ZAYIDIA_CATALOG: list[dict[str, Any]] = [
    *PROJECT_CATALOG,
    {
        "id": 202,
        "name": "Zayidia Girls School Renovation",
        "wo_ref_no": "WO-202",
        "description": "Girls school renovation in Zayidia",
    },
    {
        "id": 203,
        "name": "Zayidia Community Center",
        "wo_ref_no": "WO-203",
        "description": "Community center in Zayidia district",
    },
]


class FixedIntentAnalyzer:
    """Return a predetermined intent without calling Claude."""

    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    async def analyze(self, query: str, context: ContextStack) -> Intent:
        del query, context
        return self.intent


class FixedContextStackBuilder(ContextStackBuilder):
    """Return a fixed context stack for deterministic integration tests."""

    def __init__(self, stack: ContextStack) -> None:
        self._stack = stack

    async def build(self, user: CurrentUser, request: Any) -> ContextStack:
        del user
        return replace(
            self._stack,
            conversation=ConversationContext(
                session_id=getattr(request, "session_id", None),
                message=getattr(request, "message", ""),
            ),
        )


class StubProactiveIntelligence(ProactiveIntelligence):
    """Skip Claude calls during integration tests."""

    async def anticipate(self, synthesized: Any, intent: Intent, context: ContextStack) -> ProactiveActions:
        del synthesized, intent, context
        return ProactiveActions()

    def schedule_precompute(self, proactive: ProactiveActions, **kwargs: Any) -> ProactiveActions:
        del kwargs
        return proactive


class RawSyntaxSynthesizer(ResultSynthesizer):
    """Inject forbidden raw syntax so the quality gate must retry."""

    def synthesize(self, execution_result: Any, intent: Intent) -> SynthesizedResult:
        base = super().synthesize(execution_result, intent)
        return SynthesizedResult(
            text=f"{base.text} amount_total:sum",
            visualization=base.visualization,
        )


class ArabicSynthesizer(ResultSynthesizer):
    """Return Arabic narrative for language integration tests."""

    def synthesize(self, execution_result: Any, intent: Intent) -> SynthesizedResult:
        del execution_result, intent
        return SynthesizedResult(
            text="إجمالي الإيرادات لهذا الشهر: ١٥٠٬٠٠٠ درهم إماراتي.",
            visualization={
                "visual_type": "DATA_TABLE",
                "title": "تقرير الأرباح والخسائر",
                "data": {"rows": [["الإيرادات", "150000"]]},
            },
        )


def _super_admin() -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        id=5001,
        file_id="USR-5001",
        name="Regular User",
        language="en",
        is_super_admin=False,
        is_active=True,
        roles=("user",),
        permissions=frozenset(),
        department_ids=(2,),
        department_codes=("Operations",),
    )


def _stack_for_user(user: CurrentUser, *, message: str = "test") -> ContextStack:
    level = 100 if user.is_super_admin else 30
    role = "super_admin" if user.is_super_admin else "regular_user"
    return _make_context_stack(primary_role=role, level=level)


def _aggregate_rows(client: str, amount: float) -> dict[str, Any]:
    return {
        "partner_id": [1, client],
        "amount_total:sum": amount,
    }


def _compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 2026 vs Q1 2025 by top 5 clients",
        estimated_complexity="complex",
        expected_output="chart",
    )


def _build_pl_strategy() -> Strategy:
    return Strategy(
        steps=[
            ExecutionStep(
                step_number=1,
                description="Fetch P&L for last 3 months",
                tool="get_financial_report",
                tool_input={
                    "report_type": "pandl",
                    "date_from": "2026-04-01",
                    "date_to": "2026-06-30",
                },
                depends_on=[],
                parallel_with=[],
                expected_output="summary",
                fallback_if_fails="use_tool:get_trial_balance:{}",
            ),
        ],
        synthesis_approach="Summarize P&L totals for the period",
        quality_checks=["Totals are present"],
        estimated_duration_ms=2000,
    )


def _handler(
    *,
    intent: Intent,
    stack: ContextStack,
    telemetry_store: InMemoryTelemetryStore | None = None,
    entity_catalog: list[dict[str, Any]] | None = None,
    synthesizer: ResultSynthesizer | None = None,
) -> IntelligentQueryHandler:
    store = telemetry_store or InMemoryTelemetryStore()
    resolver = EntityResolver(MockProjectSearch(entity_catalog or PROJECT_CATALOG))
    return IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(stack),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=resolver,
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=store),
        synthesizer=synthesizer or ResultSynthesizer(),
    )


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


@pytest.mark.asyncio
async def test_zayidia_boys_school_costs_requires_confirmation_then_fetches() -> None:
    """Regression: discovery first, financial KPI only after user confirms project."""
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
        estimated_complexity="moderate",
    )
    executor = MockToolExecutor(
        responses={
            ("get_project_expense_summary", 1): {
                "status": "success",
                "project_id": 201,
                "project_name": "Zayidia Boys School Renovation",
                "currency": "AED",
                "wo_amount": 200000,
                "total_expenses": 125000,
                "spend_percent_of_wo": 62.5,
                "top_expenses": [{"name": "Civil", "amount": 50000, "percent": 40}],
                "expense_lines": [],
                "variance_amount": 75000,
                "is_over_budget": False,
                "_source": "project_expense_summary",
                "status": "success",
            },
        },
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[PROJECT_CATALOG[3]],
    )
    first = await handler.handle(
        "show me Zayidia Boys School costs",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
    )

    assert first.awaiting_clarification
    assert first.tools_called == []
    assert first.clarification is not None
    assert first.clarification.get("options")
    assert any(
        "zayidia" in str(option.get("label", "")).lower()
        for option in first.clarification["options"]
    )

    confirmed = [
        ConfirmedEntityRef(
            type="project",
            id=201,
            name="Zayidia Boys School Renovation",
        ),
    ]
    second = await handler.handle(
        "show me Zayidia Boys School costs",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
        confirmed_entities=confirmed,
    )

    assert not second.awaiting_clarification
    assert second.resolved_entities
    assert second.resolved_entities[0]["action"] == "user_confirmed"
    assert second.tools_called == ["get_project_expense_summary"]
    assert executor.calls[0][1].get("project_id") == 201
    assert "database" not in second.text.lower()
    assert "266 projects" not in second.text.lower()


@pytest.mark.asyncio
async def test_villa_maintenance_expense_uses_mobile_summary_after_confirm() -> None:
    """Regression: financial-subject expense queries route to get_project_expense_summary."""
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Villa Maintenance No. 34 expense",
        entities=[
            EntityReference(type="project", value="Villa Maintenance No. 34", confidence=0.9),
        ],
        estimated_complexity="simple",
    )
    villa_project = {
        "id": 31034,
        "name": "Villa Maintenance No. 34",
        "wo_ref_no": "WO-VM-34",
        "description": "Villa maintenance contract",
    }
    executor = MockToolExecutor(
        responses={
            ("get_project_expense_summary", 1): {
                "status": "success",
                "project_id": 31034,
                "project_name": "Villa Maintenance No. 34",
                "currency": "AED",
                "wo_amount": 500000,
                "total_expenses": 320000,
                "spend_percent_of_wo": 64.0,
                "top_expenses": [{"name": "Maintenance", "amount": 120000, "percent": 37.5}],
                "expense_lines": [{"label": "Labor", "amount": 80000}],
                "variance_amount": 180000,
                "is_over_budget": False,
                "_source": "project_expense_summary",
                "status": "success",
            },
        },
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[villa_project],
    )
    first = await handler.handle(
        "Villa Maintenance No. 34 expense",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
    )
    assert first.awaiting_clarification
    assert first.tools_called == []

    confirmed = [
        ConfirmedEntityRef(type="project", id=31034, name="Villa Maintenance No. 34"),
    ]
    second = await handler.handle(
        "Villa Maintenance No. 34 expense",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
        confirmed_entities=confirmed,
    )

    assert not second.awaiting_clarification
    assert second.tools_called == ["get_project_expense_summary"]
    assert executor.calls[0][1].get("project_id") == 31034
    assert (second.visualization or {}).get("visual_type") == "PROJECT_EXPENSE_SUMMARY"
    assert (second.visualization or {}).get("expense_lines")
    assert "selected period" not in second.text.lower()
    assert "W.O" in second.text or "spend" in second.text.lower()


@pytest.mark.asyncio
async def test_villa_maintenance_expense_for_this_year_uses_mobile_summary() -> None:
    """Regression: period phrase + project expense still routes to mobile summary."""
    query = "Villa Maintenance No. 34 expense i need for this year"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent=query,
        entities=[
            EntityReference(type="project", value="Villa Maintenance No. 34", confidence=0.9),
        ],
        estimated_complexity="simple",
    )
    villa_project = {
        "id": 31034,
        "name": "Villa Maintenance No. 34",
        "wo_ref_no": "WO-VM-34",
        "description": "Villa maintenance contract",
    }
    executor = MockToolExecutor(
        responses={
            ("get_project_expense_summary", 1): {
                "status": "success",
                "project_id": 31034,
                "project_name": "Villa Maintenance No. 34",
                "currency": "AED",
                "wo_amount": 500000,
                "total_expenses": 12120.16,
                "spend_percent_of_wo": 2.4,
                "top_expenses": [{"name": "Maintenance", "amount": 8000, "percent": 66.0}],
                "expense_lines": [{"label": "Labor", "amount": 4120.16}],
                "variance_amount": 487879.84,
                "is_over_budget": False,
                "_source": "project_expense_summary",
                "status": "success",
            },
        },
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[villa_project],
    )
    first = await handler.handle(
        query,
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
    )
    assert first.awaiting_clarification

    confirmed = [
        ConfirmedEntityRef(type="project", id=31034, name="Villa Maintenance No. 34"),
    ]
    second = await handler.handle(
        query,
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
        confirmed_entities=confirmed,
    )

    assert not second.awaiting_clarification
    assert second.tools_called == ["get_project_expense_summary"]
    assert (second.visualization or {}).get("visual_type") == "PROJECT_EXPENSE_SUMMARY"
    assert (second.visualization or {}).get("expense_lines")
    assert "selected period" not in second.text.lower()
    assert "12,120.16" in second.text or "12120" in second.text.replace(",", "")
    assert "calendar period" in second.text.lower() or "W.O-based" in second.text


@pytest.mark.asyncio
async def test_villa_cost_breakdown_follow_up_reuses_session_project() -> None:
    """Follow-up breakdown uses last project from session scope without re-asking."""
    from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
    from gateway.session_scope import SessionScopeStore

    session_id = "villa-breakdown-follow-up"
    SessionScopeStore.update(
        session_id,
        project_id=31034,
        project_name="Villa Maintenance No. 34",
        last_expense_summary_project_id=31034,
        confirmed_entities={
            "project": {"id": 31034, "name": "Villa Maintenance No. 34"},
        },
    )

    follow_up = "show me cost break down as well"
    intent = Intent(
        primary_action="analyze",
        subject_area="project",
        specific_intent=follow_up,
        requires_clarification=True,
        clarification_question="Which project would you like to see the cost breakdown for?",
        estimated_complexity="simple",
    )
    executor = MockToolExecutor(
        responses={
            ("get_project_expense_breakdown", 1): {
                "status": "success",
                "project_id": 31034,
                "project_name": "Villa Maintenance No. 34",
                "currency": "AED",
                "grand_total": 11053.15,
                "group_count": 1,
                "groups": [
                    {
                        "code": "MG01",
                        "name": "Salary",
                        "total": 11053.15,
                        "subgroups": [
                            {
                                "code": "SG01",
                                "name": "Labor",
                                "total": 11053.15,
                                "accounts": [
                                    {
                                        "code": "55002",
                                        "name": "LABER WAGES",
                                        "total": 11053.15,
                                    },
                                ],
                            },
                        ],
                    },
                ],
                "_source": "project_expense_breakdown_mobile",
            },
        },
    )
    handler = IntelligentQueryHandler(
        context_builder=ContextStackBuilder(),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch([])),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        follow_up,
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
        session_id=session_id,
    )

    assert not response.awaiting_clarification
    assert "Which project" not in response.text
    assert response.tools_called == ["get_project_expense_breakdown"]
    assert executor.calls[0][1].get("project_id") == 31034
    assert (response.visualization or {}).get("visual_type") == "PROJECT_EXPENSE_BREAKDOWN"
    assert (response.visualization or {}).get("groups")


@pytest.mark.asyncio
async def test_general_maintenance_returns_candidates() -> None:
    """search_entity intent returns candidate list, not a random project's expense data."""
    intent = Intent(
        primary_action="search_entity",
        subject_area="project",
        specific_intent="general maintenance",
        entities=[],
        estimated_complexity="simple",
    )
    query = "show me general maintenance projects"
    executor = MockToolExecutor(
        responses={
            ("search_entities", 1): {
                "status": "success",
                "_source": "search_entities",
                "query": "general maintenance",
                "total_matches": 2,
                "candidates": [
                    {
                        "id": 501,
                        "name": "General Maintenance Contract A",
                        "entity_type": "project",
                        "wo_ref_no": "WO-501",
                    },
                    {
                        "id": 502,
                        "name": "General Maintenance Contract B",
                        "entity_type": "project",
                        "wo_ref_no": "WO-502",
                    },
                ],
            },
        },
    )
    handler = IntelligentQueryHandler(
        context_builder=ContextStackBuilder(),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch([])),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )

    response = await handler.handle(
        query,
        _super_admin(),
        adapter=object(),
        deep_think=True,
        executor=executor,
        session_id="general-maintenance-search",
    )

    assert not response.awaiting_clarification
    assert response.tools_called == ["search_entities"]
    assert "get_project_expense_summary" not in response.tools_called
    assert (response.visualization or {}).get("visual_type") == "ENTITY_CANDIDATES"
    assert len((response.visualization or {}).get("candidates") or []) == 2


@pytest.mark.asyncio
async def test_payslip_query_honest_unavailable_response() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my last payslip",
        out_of_scope=True,
        out_of_scope_reason="hr.payslips is unavailable. Use the HR portal directly at hr.elrace.com",
    )
    handler = _handler(intent=intent, stack=_stack_for_user(_super_admin()))
    response = await handler.handle(
        "what is my last payslip",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        session_id="sess-payslip",
    )

    assert response.failure_mode == "tool_not_available"
    lowered = response.text.lower()
    assert "payslip" in lowered or "payroll" in lowered
    assert "hr.elrace.com" in lowered or "hr portal" in lowered
    assert "q3 2026" in lowered
    assert not contains_fabricated_excuse(response.text)
    assert response.strategy_step_count == 0


@pytest.mark.asyncio
async def test_national_guard_requires_confirmation_before_expenses() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="national guard project expense report for last month",
        entities=[EntityReference(type="project", value="national guard", confidence=0.9)],
        expected_output="summary",
    )
    handler = _handler(intent=intent, stack=_stack_for_user(_super_admin()))
    response = await handler.handle(
        "give me national guard project expense report for last month",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    assert response.tools_called == []
    assert response.clarification is not None
    assert response.clarification.get("options")


@pytest.mark.asyncio
async def test_simple_pl_query_completes_under_five_seconds() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show P&L for last 3 months",
        expected_output="summary",
    )
    executor = MockToolExecutor(
        responses={
            ("get_financial_report", 1): {
                "report_type": "pandl",
                "total_revenue": 500000,
                "total_expenses": 350000,
                "net_profit": 150000,
            },
        },
    )
    handler = _handler(intent=intent, stack=_stack_for_user(_super_admin()))
    started = time.perf_counter()
    response = await handler.handle(
        "Show P&L for last 3 months",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=_build_pl_strategy(),
        executor=executor,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert response.execution_duration_ms < 5000
    assert response.tools_called == ["get_financial_report"]
    assert response.text


@pytest.mark.asyncio
async def test_complex_comparison_orchestrates_multiple_tools() -> None:
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    handler = _handler(intent=_compare_intent(), stack=_stack_for_user(_super_admin()))
    response = await handler.handle(
        "Compare top 5 projects revenue this year vs last year",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert len(response.tools_called) == 2
    assert response.tools_called.count("group_and_aggregate") == 2
    assert response.strategy_step_count == 2
    assert response.visualization is not None
    assert response.visualization["visual_type"] in {"DATA_TABLE", "BAR_CHART"}


@pytest.mark.asyncio
async def test_quality_gate_retries_on_bad_response() -> None:
    executor = MockToolExecutor(
        responses={
            ("get_financial_report", 1): {
                "rows": [{"label": "Net Profit", "amount": 50}],
                "net_profit": 50,
            },
        },
    )
    handler = _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent="Show P&L",
        ),
        stack=_stack_for_user(_super_admin()),
        synthesizer=RawSyntaxSynthesizer(),
    )
    response = await handler.handle(
        "Show P&L for last 3 months",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=_build_pl_strategy(),
        executor=executor,
    )

    assert response.quality_checks_total >= 8
    assert response.quality_checks_passed < response.quality_checks_total


@pytest.mark.asyncio
async def test_telemetry_recorded_for_every_query() -> None:
    store = InMemoryTelemetryStore()
    handler = _handler(
        intent=_compare_intent(),
        stack=_stack_for_user(_super_admin()),
        telemetry_store=store,
    )
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    assert response.interaction_id
    assert len(store.records) == 1
    record = store.records[0]
    assert record.interaction_id == response.interaction_id
    assert record.user_query.startswith("Compare revenue")
    assert record.response_text == response.text


@pytest.mark.asyncio
async def test_arabic_query_returns_arabic_response() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="أرني تقرير الأرباح والخسائر لهذا الشهر",
        expected_output="summary",
    )
    executor = MockToolExecutor(
        responses={
            ("get_financial_report", 1): {
                "rows": [{"label": "Net Profit", "amount": 40000}],
                "total_revenue": 150000,
                "net_profit": 40000,
            },
        },
    )
    handler = _handler(
        intent=intent,
        stack=_make_context_stack(primary_role="super_admin", level=100),
        synthesizer=ArabicSynthesizer(),
    )
    response = await handler.handle(
        "أرني تقرير الأرباح والخسائر لهذا الشهر",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        language="ar",
        strategy_override=_build_pl_strategy(),
        executor=executor,
    )

    assert _has_arabic(response.text)
    assert response.language == "ar"
    assert response.visualization is not None
    assert _has_arabic(str(response.visualization.get("title", "")))


@pytest.mark.asyncio
async def test_super_admin_also_requires_entity_confirmation() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="national guard expenses",
        entities=[EntityReference(type="project", value="national guard", confidence=0.9)],
    )
    handler = _handler(intent=intent, stack=_stack_for_user(_super_admin()))
    response = await handler.handle(
        "national guard expenses last month",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    assert response.tools_called == []
    assert response.clarification is not None


@pytest.mark.asyncio
async def test_regular_user_gets_conservative_entity_resolution() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="Show me the Zayidia project costs",
        entities=[EntityReference(type="project", value="Zayidia", confidence=0.85)],
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_regular_user()),
        entity_catalog=ZAYIDIA_CATALOG,
    )
    response = await handler.handle(
        "Show me the Zayidia project costs",
        _regular_user(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    combined = f"{response.text} {response.clarification}".lower()
    assert "zayidia" in combined
    assert "confirm" in combined or response.failure_mode == "ambiguous_reference"


@pytest.mark.asyncio
async def test_part_xii_canonical_scenarios() -> None:
    """Scenarios A–J from AI_CORE_INTELLIGENCE_ARCHITECTURE.md PART XII."""

    # A — Payslip
    payslip = await _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="hr",
            specific_intent="what is my last payslip",
            out_of_scope=True,
            out_of_scope_reason="hr.payslips is unavailable. Use the HR portal directly at hr.elrace.com",
        ),
        stack=_stack_for_user(_super_admin()),
    ).handle("what is my last payslip", _super_admin(), adapter=object(), deep_think=True)
    assert not contains_fabricated_excuse(payslip.text)
    assert "hr" in payslip.text.lower()

    # B — Super admin National Guard
    ng_intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="national guard expense report",
        entities=[EntityReference(type="project", value="national guard", confidence=0.9)],
    )
    ng = await _handler(intent=ng_intent, stack=_stack_for_user(_super_admin())).handle(
        "give me national guard project expense report for last month",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )
    assert ng.awaiting_clarification
    assert ng.tools_called == []

    # C — Ambiguous Zayidia (regular user)
    zayidia = await _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="Zayidia project costs",
            entities=[EntityReference(type="project", value="Zayidia", confidence=0.8)],
        ),
        stack=_stack_for_user(_regular_user()),
        entity_catalog=ZAYIDIA_CATALOG,
    ).handle("Show me the Zayidia project costs", _regular_user(), adapter=object(), deep_think=True)
    assert zayidia.awaiting_clarification or zayidia.failure_mode == "ambiguous_reference"

    # D — Forecast out of scope
    forecast = await _handler(
        intent=Intent(
            primary_action="analyze",
            subject_area="financial",
            specific_intent="Forecast next month's cash position",
            out_of_scope=True,
            out_of_scope_reason="Cash flow forecasting is planned but not live yet.",
        ),
        stack=_stack_for_user(_super_admin()),
    ).handle("Forecast next month's cash position", _super_admin(), adapter=object(), deep_think=True)
    assert forecast.failure_mode in {"feature_coming_soon", "out_of_scope"}
    assert "forecast" in forecast.text.lower() or "historical" in forecast.text.lower()

    # E — Multi-step comparison
    compare = await _handler(
        intent=_compare_intent(),
        stack=_stack_for_user(_super_admin()),
    ).handle(
        "Compare top 5 projects revenue this year vs last year",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=build_revenue_comparison_strategy(),
        executor=MockToolExecutor(
            responses={
                ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
                ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
            },
        ),
    )
    assert compare.strategy_step_count >= 2
    assert compare.visualization is not None

    # F — Permission restricted
    restricted = await _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent="Show me all department budgets",
            out_of_scope=True,
            out_of_scope_reason=(
                "Department budget visibility is limited to your department. "
                "Contact your system administrator for broader access."
            ),
        ),
        stack=_stack_for_user(_regular_user()),
    ).handle("Show me all department budgets", _regular_user(), adapter=object(), deep_think=True)
    assert "department" in restricted.text.lower() or "access" in restricted.text.lower()

    # G — Vague date / period
    vague = await _handler(
        intent=Intent(
            primary_action="analyze",
            subject_area="financial",
            specific_intent="How are we doing?",
            requires_clarification=True,
            clarification_question="Which period should I use — this month, last 3 months, or year to date?",
        ),
        stack=_stack_for_user(_regular_user()),
    ).handle("How are we doing?", _regular_user(), adapter=object(), deep_think=True)
    assert vague.awaiting_clarification
    assert "period" in vague.text.lower() or "month" in vague.text.lower()

    # H — Arabic P&L
    arabic = await _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent="أرني تقرير الأرباح والخسائر لهذا الشهر",
        ),
        stack=_make_context_stack(primary_role="super_admin", level=100),
        synthesizer=ArabicSynthesizer(),
    ).handle(
        "أرني تقرير الأرباح والخسائر لهذا الشهر",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        language="ar",
        strategy_override=_build_pl_strategy(),
        executor=MockToolExecutor(
            responses={
                ("get_financial_report", 1): {
                    "rows": [{"label": "Net Profit", "amount": 40000}],
                    "net_profit": 40000,
                },
            },
        ),
    )
    assert _has_arabic(arabic.text)

    # I — Complex analytical (margin variance)
    margin_intent = Intent(
        primary_action="analyze",
        subject_area="financial",
        specific_intent="Why is our margin lower this month?",
        estimated_complexity="complex",
        expected_output="explanation",
    )
    margin = await _handler(
        intent=margin_intent,
        stack=_stack_for_user(_super_admin()),
    ).handle(
        "Why is our margin lower this month?",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        strategy_override=Strategy(
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="Current month margin",
                    tool="get_financial_report",
                    tool_input={"report_type": "pandl", "date_from": "2026-06-01", "date_to": "2026-06-30"},
                    depends_on=[],
                    parallel_with=[2],
                    expected_output="summary",
                    fallback_if_fails="",
                ),
                ExecutionStep(
                    step_number=2,
                    description="Prior month margin",
                    tool="get_financial_report",
                    tool_input={"report_type": "pandl", "date_from": "2026-05-01", "date_to": "2026-05-31"},
                    depends_on=[],
                    parallel_with=[1],
                    expected_output="summary",
                    fallback_if_fails="",
                ),
            ],
            synthesis_approach="Explain margin change drivers",
            quality_checks=["Variance explained"],
            estimated_duration_ms=4000,
        ),
        executor=MockToolExecutor(
            responses={
                ("get_financial_report", 1): {
                    "total_revenue": 100000,
                    "total_expenses": 85000,
                    "net_profit": 15000,
                },
                ("get_financial_report", 2): {
                    "total_revenue": 100000,
                    "total_expenses": 70000,
                    "net_profit": 30000,
                },
            },
        ),
    )
    assert len(margin.tools_called) == 2
    assert margin.text

    # J — Follow-up continuity after confirmed project
    memory = WorkingMemory()
    memory.session_facts["confirmed_entities"] = {
        "project": {"id": 201, "name": "Zayidia Boys School Renovation"},
    }
    memory.session_facts["resolved_project_id"] = 201
    memory.remember_entity(
        "project",
        {"id": 201, "name": "Zayidia Boys School Renovation", "wo_ref_no": "WO-201"},
    )
    follow_stack = replace(
        _stack_for_user(_super_admin()),
        working_memory=memory,
    )
    follow = await _handler(
        intent=Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="Income for Zayidia Boys School",
            entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.95)],
        ),
        stack=follow_stack,
        entity_catalog=ZAYIDIA_CATALOG,
    ).handle(
        "And the income?",
        _super_admin(),
        adapter=object(),
        deep_think=True,
        confirmed_entities=[
            ConfirmedEntityRef(type="project", id=201, name="Zayidia Boys School Renovation"),
        ],
        strategy_override=Strategy(
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="Project income",
                    tool="get_project_expenses",
                    tool_input={"project_id": 201, "project_name": "Zayidia Boys School Renovation", "metric": "income"},
                    depends_on=[],
                    parallel_with=[],
                    expected_output="summary",
                    fallback_if_fails="",
                ),
            ],
            synthesis_approach="Summarize project income",
            quality_checks=["Income shown"],
            estimated_duration_ms=1000,
        ),
        executor=MockToolExecutor(
            responses={("get_project_expenses", 1): {"income": 250000, "project": "Zayidia Boys School Renovation"}},
        ),
    )
    assert "zayidia" in follow.text.lower() or follow.resolved_entities

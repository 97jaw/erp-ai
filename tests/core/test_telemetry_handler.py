"""Handler integration tests for telemetry capture (Phase 8.2)."""

from __future__ import annotations

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.intent_analyzer import Intent
from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_execution_orchestrator import MockToolExecutor
from tests.core.test_intelligent_handler import FixedIntentAnalyzer, _aggregate_rows, _compare_intent


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


@pytest.mark.asyncio
async def test_handler_records_telemetry_for_orchestrated_query() -> None:
    store = InMemoryTelemetryStore()
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_compare_intent()),
        telemetry_capture=TelemetryCapture(repository=store),
    )
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top clients",
        _super_admin(),
        adapter=object(),
        session_id="telemetry-handler-session",
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )
    assert response.interaction_id
    assert len(store.records) == 1
    assert store.records[0].interaction_id == response.interaction_id
    assert store.records[0].tools_called


@pytest.mark.asyncio
async def test_handler_records_out_of_scope_telemetry() -> None:
    store = InMemoryTelemetryStore()
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my payslip",
        out_of_scope=True,
    )
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(intent),
        telemetry_capture=TelemetryCapture(repository=store),
    )
    response = await handler.handle(
        "what is my payslip",
        _super_admin(),
        adapter=object(),
        session_id="telemetry-oos-session",
    )
    assert response.failure_mode == "tool_not_available"
    assert store.records[0].failure_mode == "tool_not_available"


@pytest.mark.asyncio
async def test_second_message_applies_follow_up_signal() -> None:
    store = InMemoryTelemetryStore()
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_compare_intent()),
        telemetry_capture=TelemetryCapture(repository=store),
    )
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
        },
    )
    session_id = "telemetry-followup-session"
    first = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top clients",
        _super_admin(),
        adapter=object(),
        session_id=session_id,
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )
    assert first.suggestions
    clicked = first.suggestions[0]
    await handler.handle(
        clicked,
        _super_admin(),
        adapter=object(),
        session_id=session_id,
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )
    assert store.records[0].next_query_within_60s == clicked

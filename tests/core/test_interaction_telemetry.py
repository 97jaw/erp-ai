"""Tests for gateway.core.interaction_telemetry (Phase 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from gateway.core.intent_analyzer import Intent
from gateway.core.interaction_telemetry import (
    InteractionTelemetry,
    normalize_message,
    suggestion_match,
    visualization_type_from,
)
from gateway.core.quality_gate import CheckResult, QualityReview
from gateway.core.strategy_planner import ExecutionStep, Strategy


def _strategy() -> Strategy:
    return Strategy(
        steps=[
            ExecutionStep(
                step_number=1,
                description="Fetch revenue",
                tool="group_and_aggregate",
                tool_input={"model": "account.move"},
                fallback_if_fails="use_tool:search_odoo:{}",
            ),
        ],
        synthesis_approach="Compare revenue periods",
        quality_checks=["no_fabrication"],
        estimated_duration_ms=3000,
    )


def test_start_creates_identifiers_and_timestamps() -> None:
    telemetry = InteractionTelemetry.start(
        user_id=42,
        session_id="session-abc",
        user_query="Show revenue by client",
        user_query_language="en",
        interaction_id="fixed-id",
    )
    assert telemetry.interaction_id == "fixed-id"
    assert telemetry.user_id == 42
    assert telemetry.session_id == "session-abc"
    assert telemetry.user_query == "Show revenue by client"
    assert isinstance(telemetry.timestamp, datetime)


def test_finalize_response_populates_output_fields() -> None:
    telemetry = InteractionTelemetry.start(user_id=1, session_id="s1", user_query="query")
    review = QualityReview(
        checks=[CheckResult(name="no_fabrication", passed=True)],
        pass_rate=1.0,
        passed=True,
    )
    telemetry.finalize_response(
        response_text="National Guard revenue increased.",
        visualization={"visual_type": "DATA_TABLE", "data": {"rows": []}},
        suggestions=["Compare with last year", "Export to Excel"],
        total_duration_ms=1200,
        orchestration_duration_ms=800,
        quality_review=review,
        tools_called=["group_and_aggregate"],
        orchestration_log=[{"tool": "group_and_aggregate", "duration_ms": 800}],
        intent=Intent(primary_action="compare", subject_area="financial", specific_intent="Revenue"),
        strategy=_strategy(),
    )
    assert telemetry.response_length == len(telemetry.response_text)
    assert telemetry.visualization_type == "DATA_TABLE"
    assert telemetry.tool_durations_ms["group_and_aggregate"] == 800
    assert telemetry.quality_passed is True


def test_to_db_record_serializes_intent_and_strategy() -> None:
    telemetry = InteractionTelemetry.start(user_id=5, session_id="s", user_query="Q")
    telemetry.intent_extracted = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Revenue",
    )
    telemetry.strategy_used = _strategy()
    record = telemetry.to_db_record()
    assert record["user_id"] == 5
    assert record["intent"]["subject_area"] == "financial"
    assert record["strategy"]["synthesis_approach"] == "Compare revenue periods"
    assert "tool_results" not in record


def test_to_db_record_excludes_raw_tool_payloads() -> None:
    telemetry = InteractionTelemetry.start(user_id=1, session_id="s", user_query="Q")
    telemetry.metadata = {"endpoint": "/chat/intelligent"}
    record = telemetry.to_db_record()
    assert "groups" not in str(record)
    assert "partner_id" not in str(record.get("metadata"))


def test_visualization_type_from_empty_is_none() -> None:
    assert visualization_type_from(None) == "NONE"
    assert visualization_type_from({"visual_type": "BAR_CHART"}) == "BAR_CHART"


def test_suggestion_match_normalizes_case_and_spacing() -> None:
    suggestions = ["Compare with last year"]
    assert suggestion_match("  compare   with last year ", suggestions) == "Compare with last year"
    assert suggestion_match("Different query", suggestions) is None


def test_normalize_message_collapses_whitespace() -> None:
    assert normalize_message("  Hello   World ") == "hello world"


def test_from_db_row_restores_metadata_from_intent_json() -> None:
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "user_id": 9,
        "session_id": "sess",
        "created_at": datetime.now(timezone.utc),
        "user_query": "Show P&L",
        "user_query_language": "en",
        "tools_called": ["get_financial_report"],
        "tool_durations_ms": {"get_financial_report": 400},
        "orchestration_log": [],
        "retries_needed": 0,
        "quality_passed": True,
        "quality_pass_rate": 0.95,
        "confidence": None,
        "response_text": "Done",
        "response_length": 4,
        "visualization_type": "FINANCIAL_REPORT",
        "suggestions_offered": [],
        "failure_mode": None,
        "cache_hit": False,
        "proactive_cache_keys": [],
        "user_satisfaction_signal": None,
        "suggestion_clicked": None,
        "next_query_within_60s": None,
        "chat_continued": False,
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_cents": 0,
        "total_duration_ms": 100,
        "orchestration_duration_ms": 80,
        "metadata": {},
        "intent": {"subject_area": "financial", "primary_action": "fetch_data"},
        "strategy": {"synthesis_approach": "Financial report"},
    }
    telemetry = InteractionTelemetry.from_db_row(row)
    assert telemetry.metadata["subject_area"] == "financial"
    assert telemetry.metadata["strategy_label"] == "Financial report"

"""Tests for gateway.core.learning_engine (Phase 8.3)."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.intent_analyzer import Intent
from gateway.core.interaction_telemetry import InteractionTelemetry
from gateway.core.learning_engine import LearningEngine, LearningPatterns
from gateway.core.strategy_planner import ExecutionStep, Strategy
from gateway.core.working_memory import WorkingMemory


def _interaction(
    *,
    user_id: int = 1,
    subject: str = "financial",
    tool: str = "group_and_aggregate",
    passed: bool = True,
    failure_mode: str | None = None,
    suggestion_clicked: str | None = None,
    cache_hit: bool = False,
    duration: int = 500,
) -> InteractionTelemetry:
    telemetry = InteractionTelemetry.start(
        user_id=user_id,
        session_id=f"session-{user_id}",
        user_query=f"Query about {subject}",
    )
    telemetry.intent_extracted = Intent(
        primary_action="fetch_data",
        subject_area=subject,
        specific_intent="Sample",
    )
    telemetry.strategy_used = Strategy(
        steps=[
            ExecutionStep(
                step_number=1,
                description="step",
                tool=tool,
                tool_input={},
                fallback_if_fails="fallback",
            ),
        ],
        synthesis_approach=f"Strategy for {subject}",
        quality_checks=[],
        estimated_duration_ms=1000,
    )
    telemetry.tools_called = [tool]
    telemetry.tool_durations_ms = {tool: duration}
    telemetry.quality_passed = passed
    telemetry.quality_pass_rate = 1.0 if passed else 0.5
    telemetry.failure_mode = failure_mode
    telemetry.suggestion_clicked = suggestion_clicked
    telemetry.cache_hit = cache_hit
    telemetry.orchestration_log = [{"tool": tool, "duration_ms": duration}]
    return telemetry


class FakeLearningStore:
    def __init__(self, rows: list[InteractionTelemetry] | None = None) -> None:
        self.rows = rows or []
        self.patterns: dict[int, dict[str, Any]] = {}
        self.jobs: list[dict[str, Any]] = []

    async def list_recent(self, *, hours: int = 24, user_id: int | None = None, limit: int = 500) -> list[Any]:
        del hours, user_id, limit
        return self.rows

    async def upsert_user_patterns(self, user_id: int, patterns: dict[str, Any]) -> None:
        self.patterns[user_id] = patterns

    async def start_learning_job(self, hours: int) -> int:
        job_id = len(self.jobs) + 1
        self.jobs.append({"id": job_id, "hours": hours, "status": "running"})
        return job_id

    async def finish_learning_job(
        self,
        job_id: int,
        *,
        status: str,
        interactions_analyzed: int,
        summary: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        self.jobs[-1].update(
            {
                "status": status,
                "interactions_analyzed": interactions_analyzed,
                "summary": summary,
                "error_message": error_message,
            },
        )


def test_find_common_failures_counts_failure_modes() -> None:
    rows = [
        _interaction(failure_mode="tool_not_available"),
        _interaction(failure_mode="tool_not_available"),
        _interaction(passed=False),
    ]
    failures = LearningEngine._find_common_failures(rows)
    assert failures[0]["failure_mode"] == "tool_not_available"
    assert failures[0]["count"] == 2


def test_find_successful_strategies_groups_by_synthesis_approach() -> None:
    rows = [_interaction(subject="financial"), _interaction(subject="financial")]
    strategies = LearningEngine._find_successful_strategies(rows)
    assert strategies[0]["success_count"] == 2


def test_find_user_patterns_tracks_subjects_and_tools() -> None:
    rows = [_interaction(user_id=10, subject="financial"), _interaction(user_id=10, subject="project")]
    patterns = LearningEngine._find_user_patterns(rows)
    assert "10" in patterns
    assert "financial" in patterns["10"]["top_subject_areas"]
    assert patterns["10"]["recent_query_count"] == 2


def test_analyze_tool_performance_averages_durations() -> None:
    rows = [
        _interaction(tool="group_and_aggregate", duration=200),
        _interaction(tool="group_and_aggregate", duration=600),
    ]
    stats = LearningEngine._analyze_tool_performance(rows)
    assert stats[0]["tool"] == "group_and_aggregate"
    assert stats[0]["avg_duration_ms"] == 400


def test_detect_quality_drift_reports_pass_and_cache_rates() -> None:
    rows = [_interaction(cache_hit=True), _interaction(passed=False)]
    drift = LearningEngine._detect_quality_drift(rows)
    assert drift["sample_size"] == 2
    assert drift["cache_hit_rate"] == 0.5


def test_apply_to_working_memory_merges_patterns() -> None:
    memory = WorkingMemory(user_patterns={"existing": "value"})
    LearningEngine.apply_to_working_memory(memory, {"preferred_tools": ["group_and_aggregate"]})
    assert memory.user_patterns["existing"] == "value"
    assert memory.user_patterns["preferred_tools"] == ["group_and_aggregate"]


@pytest.mark.asyncio
async def test_learn_from_recent_persists_user_patterns() -> None:
    store = FakeLearningStore([_interaction(user_id=55, suggestion_clicked="Export table")])
    engine = LearningEngine(store)
    patterns = await engine.learn_from_recent(hours=24)
    assert patterns.user_specific_patterns["55"]["suggestion_click_rate"] > 0
    assert 55 in store.patterns
    assert store.jobs[-1]["status"] == "success"


@pytest.mark.asyncio
async def test_learn_from_recent_marks_job_failed_on_error() -> None:
    class BrokenStore(FakeLearningStore):
        async def list_recent(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("db down")

    store = BrokenStore()
    engine = LearningEngine(store)
    with pytest.raises(RuntimeError):
        await engine.learn_from_recent(hours=1)
    assert store.jobs[-1]["status"] == "failed"


def test_learning_patterns_to_dict_is_json_safe() -> None:
    patterns = LearningPatterns(common_failures=[{"failure_mode": "timeout", "count": 1}])
    payload = patterns.to_dict()
    assert payload["common_failures"][0]["count"] == 1

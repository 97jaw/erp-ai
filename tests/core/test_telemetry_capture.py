"""Tests for gateway.core.telemetry_capture (Phase 8.2)."""

from __future__ import annotations

import pytest

from gateway.core.interaction_telemetry import InteractionTelemetry
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture


@pytest.mark.asyncio
async def test_record_stores_interaction_in_memory() -> None:
    store = InMemoryTelemetryStore()
    capture = TelemetryCapture(repository=store)
    telemetry = InteractionTelemetry.start(user_id=1, session_id="s1", user_query="Hello")
    telemetry.response_text = "Hi"
    await capture.record(telemetry)
    assert len(store.records) == 1
    assert store.records[0].user_query == "Hello"


@pytest.mark.asyncio
async def test_disabled_capture_does_not_require_repository() -> None:
    capture = TelemetryCapture(enabled=False)
    telemetry = InteractionTelemetry.start(user_id=1, session_id="s1", user_query="Q")
    await capture.record(telemetry)


@pytest.mark.asyncio
async def test_apply_follow_up_marks_chat_continued() -> None:
    store = InMemoryTelemetryStore()
    capture = TelemetryCapture(repository=store)
    first = InteractionTelemetry.start(user_id=7, session_id="sess", user_query="First")
    first.suggestions_offered = ["Show revenue by client"]
    first.response_text = "Done"
    await capture.record(first)
    await capture.apply_follow_up_signals(user_id=7, session_id="sess", next_query="Second question")
    assert store.records[0].chat_continued is True
    assert store.records[0].next_query_within_60s == "Second question"


@pytest.mark.asyncio
async def test_apply_follow_up_detects_suggestion_click() -> None:
    store = InMemoryTelemetryStore()
    capture = TelemetryCapture(repository=store)
    first = InteractionTelemetry.start(user_id=7, session_id="sess", user_query="Revenue")
    first.suggestions_offered = ["Show revenue by client for last quarter"]
    await capture.record(first)
    await capture.apply_follow_up_signals(
        user_id=7,
        session_id="sess",
        next_query="Show revenue by client for last quarter",
    )
    assert store.records[0].suggestion_clicked == "Show revenue by client for last quarter"


@pytest.mark.asyncio
async def test_record_noop_when_repository_missing() -> None:
    capture = TelemetryCapture(repository=None, enabled=True)
    telemetry = InteractionTelemetry.start(user_id=1, session_id="s", user_query="Q")
    await capture.record(telemetry)


class _UsageSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def record(self, user_id: int, *, queries: int = 0, tokens: int = 0, **kwargs) -> None:
        self.calls.append({"user_id": user_id, "queries": queries, "tokens": tokens})


@pytest.mark.asyncio
async def test_record_updates_usage_stats_when_configured() -> None:
    store = InMemoryTelemetryStore()
    usage = _UsageSpy()
    capture = TelemetryCapture(repository=store, usage_repository=usage)
    telemetry = InteractionTelemetry.start(user_id=3, session_id="s", user_query="Q")
    telemetry.tokens_input = 100
    telemetry.tokens_output = 50
    await capture.record(telemetry)
    assert usage.calls == [{"user_id": 3, "queries": 1, "tokens": 150}]


@pytest.mark.asyncio
async def test_multiple_records_preserve_order() -> None:
    store = InMemoryTelemetryStore()
    capture = TelemetryCapture(repository=store)
    for index in range(3):
        telemetry = InteractionTelemetry.start(
            user_id=1,
            session_id="s",
            user_query=f"Query {index}",
        )
        await capture.record(telemetry)
    assert [item.user_query for item in store.records] == ["Query 0", "Query 1", "Query 2"]


@pytest.mark.asyncio
async def test_follow_up_without_prior_record_is_safe() -> None:
    store = InMemoryTelemetryStore()
    capture = TelemetryCapture(repository=store)
    await capture.apply_follow_up_signals(user_id=1, session_id="missing", next_query="Next")

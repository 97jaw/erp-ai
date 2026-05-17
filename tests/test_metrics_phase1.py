from __future__ import annotations

from gateway.metrics import (
    REGISTRY,
    metrics_payload,
    normalize_endpoint,
    record_claude_response,
    record_tool_execution,
)


def test_normalize_endpoint_replaces_uuid() -> None:
    path = "/conversations/a0c4fd1d-0fb6-4cc8-b268-46a0935a9951"
    assert normalize_endpoint(path) == "/conversations/{id}"


def test_metrics_payload_contains_ooa_metrics() -> None:
    record_tool_execution("calculate", 0.05, status="success", cached=False)
    body = metrics_payload().decode("utf-8")
    assert "ooa_tool_executions_total" in body
    assert "ooa_api_requests_total" in body


def test_record_claude_response() -> None:
    class Usage:
        input_tokens = 100
        output_tokens = 50

    class Response:
        usage = Usage()
        stop_reason = "end_turn"

    record_claude_response(Response(), 1.2, model="claude-sonnet-4-20250514")
    body = metrics_payload().decode("utf-8")
    assert "ooa_ai_tokens_consumed_total" in body
    assert "ooa_ai_cost_cents_total" in body

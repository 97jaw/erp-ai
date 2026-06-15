"""Tests for Claude history sanitization (no tool_calls in API payload)."""

from __future__ import annotations

from gateway.agent.conversation_persistence import _sanitize_claude_messages


def test_sanitize_strips_tool_calls() -> None:
    raw = [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "pick one",
            "tool_calls": {"ui_blocks": [{"type": "pill_select", "options": []}]},
        },
    ]
    cleaned = _sanitize_claude_messages(raw)
    assert cleaned == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "pick one"},
    ]


def test_sanitize_skips_empty_content() -> None:
    raw = [{"role": "assistant", "content": "   "}]
    assert _sanitize_claude_messages(raw) == []

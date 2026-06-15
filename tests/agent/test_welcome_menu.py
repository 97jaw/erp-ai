"""Tests for welcome greeting preflight."""

from __future__ import annotations

from types import SimpleNamespace

from gateway.agent.preflight import run_chat_preflight
from gateway.agent.welcome_menu import welcome_preflight_result


def test_welcome_preflight_has_icons() -> None:
    result = welcome_preflight_result(language="en")
    assert result.ui_blocks
    options = result.ui_blocks[0]["options"]
    assert options[0].get("icon")
    assert options[0]["label"] == "Financial Reports"


def test_hi_triggers_welcome_preflight() -> None:
    user = SimpleNamespace(name="Jawad")
    result = run_chat_preflight("Hi", session_id="sess-welcome", user=user)
    assert result is not None
    assert "explore" in result.text.lower() or "Hello" in result.text

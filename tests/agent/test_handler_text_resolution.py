"""Tests for agent handler final text resolution fallbacks."""

from __future__ import annotations

from types import SimpleNamespace

from gateway.agent.handler import _resolve_final_text, _ui_block_prompt


def test_ui_block_prompt_from_picker() -> None:
    blocks = [{"type": "pill_select", "prompt": "What would you like to explore today?", "options": []}]
    assert _ui_block_prompt(blocks) == "What would you like to explore today?"


def test_resolve_final_text_prefers_streamed_text() -> None:
    text = _resolve_final_text(
        streamed_text="Hello there",
        last_response=None,
        ui_blocks=[],
        visualization=None,
        tools_called=[],
        language="en",
        empty_fallback="I could not prepare a response.",
    )
    assert text == "Hello there"


def test_resolve_final_text_falls_back_to_ui_block_prompt() -> None:
    text = _resolve_final_text(
        streamed_text="",
        last_response=None,
        ui_blocks=[{"type": "pill_select", "prompt": "Pick a module", "options": []}],
        visualization=None,
        tools_called=["show_ui_block", "add_suggestions"],
        language="en",
        empty_fallback="I could not prepare a response.",
    )
    assert text == "Pick a module"


def test_resolve_final_text_falls_back_after_data_tools() -> None:
    text = _resolve_final_text(
        streamed_text="",
        last_response=None,
        ui_blocks=[],
        visualization=None,
        tools_called=["search_entities", "get_project_expense_summary"],
        language="en",
        empty_fallback="I could not prepare a response.",
    )
    assert "gathered the data" in text.lower()


def test_resolve_final_text_extracts_from_last_response() -> None:
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Summary with figures.")]
    )
    text = _resolve_final_text(
        streamed_text="",
        last_response=response,
        ui_blocks=[],
        visualization=None,
        tools_called=[],
        language="en",
        empty_fallback="I could not prepare a response.",
    )
    assert text == "Summary with figures."

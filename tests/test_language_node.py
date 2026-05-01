"""
OOA Phase 2 — Language Node Tests
===================================
File   : tests/test_language_node.py

Tests for LanguageDetectionNode.
Uses mocking so no real API calls are made during testing.
"""

import pytest
from unittest.mock import MagicMock, patch
from core.nodes.language_node import LanguageDetectionNode
from core.state import AgentState, OdooVersion, SessionState, TurnState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(raw_input: str = "", language: str = "en") -> AgentState:
    session = SessionState(
        odoo_user_id = 1,
        odoo_version = OdooVersion.V14,
        odoo_url     = "http://localhost:8069",
        user_language= language,
    )
    turn = TurnState(raw_input=raw_input, turn_number=1)
    return AgentState(session=session, turn=turn)


def make_node() -> LanguageDetectionNode:
    return LanguageDetectionNode(api_key="sk-ant-test-fake-key-for-testing")


def mock_claude_response(text: str) -> MagicMock:
    """Creates a mock Anthropic API response."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLanguageDetectionNode:

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_detects_english(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("en")
        )
        node   = make_node()
        state  = make_state("What is our total sales today?")
        result = node(state)
        assert result["turn"]["input_language"] == "en"
        assert result["session"]["user_language"] == "en"
        assert result["_language_direction"] == "ltr"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_detects_arabic(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("ar")
        )
        node   = make_node()
        state  = make_state("ما هو إجمالي المبيعات اليوم؟")
        result = node(state)
        assert result["turn"]["input_language"] == "ar"
        assert result["_language_direction"] == "rtl"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_detects_urdu(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("ur")
        )
        node   = make_node()
        state  = make_state("آج کی سیلز کیا ہے؟")
        result = node(state)
        assert result["turn"]["input_language"] == "ur"
        assert result["_language_direction"] == "rtl"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_defaults_to_english_on_unknown_response(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("fr")  # French — not supported
        )
        node   = make_node()
        state  = make_state("Bonjour")
        result = node(state)
        assert result["turn"]["input_language"] == "en"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_defaults_to_english_on_api_failure(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.side_effect = (
            Exception("Connection timeout")
        )
        node   = make_node()
        state  = make_state("Some input")
        result = node(state)
        # Must not crash — must default to English
        assert result["turn"]["input_language"] == "en"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_empty_input_uses_session_language(self, mock_anthropic):
        node   = make_node()
        state  = make_state(raw_input="", language="ar")
        result = node(state)
        # No API call should be made for empty input
        mock_anthropic.return_value.messages.create.assert_not_called()
        assert result["turn"]["input_language"] == "ar"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_arabic_is_rtl(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("ar")
        )
        result = make_node()(make_state("مرحبا"))
        assert result["_language_direction"] == "rtl"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_urdu_is_rtl(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("ur")
        )
        result = make_node()(make_state("سلام"))
        assert result["_language_direction"] == "rtl"

    @patch("core.nodes.language_node.anthropic.Anthropic")
    def test_english_is_ltr(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_response("en")
        )
        result = make_node()(make_state("Hello"))
        assert result["_language_direction"] == "ltr"

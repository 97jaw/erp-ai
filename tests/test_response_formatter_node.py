"""
OOA Phase 2 — Response Formatter Node Tests
=============================================
File   : tests/test_response_formatter_node.py
"""

import pytest
from unittest.mock import MagicMock, patch

from core.nodes.response_formatter_node import ResponseFormatterNode
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    IntentRecord,
    IntentType,
    OdooVersion,
    SessionState,
    TurnState,
    VisualType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    raw_input       : str = "Show me sales",
    language        : str = "en",
    odoo_response   : any = None,
    error_state     : ErrorState | None = None,
    intent_type     : IntentType = IntentType.KPI,
    visualization   : dict | None = None,
) -> AgentState:
    session = SessionState(
        odoo_user_id  = 1,
        odoo_version  = OdooVersion.V14,
        odoo_url      = "http://localhost:8069",
        user_language = language,
        active_domain = "sale.order",
    )
    turn = TurnState(
        raw_input            = raw_input,
        turn_number          = 4,
        input_language       = language,
        last_odoo_response   = odoo_response,
        error_state          = error_state,
        visualization_payload= visualization,
        turn_intent          = IntentRecord(
            intent_type        = intent_type,
            confidence_score   = 0.90,
            classified_at_turn = 4,
        ),
    )
    return AgentState(session=session, turn=turn)


def make_node() -> ResponseFormatterNode:
    return ResponseFormatterNode(api_key="sk-ant-fake-test-key")


def mock_claude_text(text: str) -> MagicMock:
    mock_content      = MagicMock()
    mock_content.text = text
    mock_response     = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResponseFormatterNode:

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_successful_english_response(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("Total sales this quarter is PKR 125,000.")
        )
        node  = make_node()
        state = make_state(
            odoo_response={"label": "Total Sales", "value": 125000}
        )
        result = node(state)

        text = result["turn"]["last_odoo_response"]["text"]
        assert "125,000" in text
        assert result["turn"]["last_odoo_response"]["language"] == "en"

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_arabic_response(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("إجمالي المبيعات هذا الشهر هو ١٢٥٬٠٠٠ روبية.")
        )
        node  = make_node()
        state = make_state(
            language      = "ar",
            odoo_response = {"label": "Total Sales", "value": 125000},
        )
        result = node(state)

        assert result["turn"]["last_odoo_response"]["language"] == "ar"

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_urdu_response(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("اس مہینے کی کل فروخت ١٢٥٬٠٠٠ روپے ہے۔")
        )
        node  = make_node()
        state = make_state(
            language      = "ur",
            odoo_response = {"label": "Total Sales", "value": 125000},
        )
        result = node(state)

        assert result["turn"]["last_odoo_response"]["language"] == "ur"

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_error_state_returns_error_message(self, mock_anthropic):
        error = ErrorState(
            severity    = ErrorSeverity.RECOVERABLE,
            source_node = "RAGNode",
            message     = "timeout",
        )
        node  = make_node()
        state = make_state(
            error_state = error,
            visualization = {
                "visual_type": "ERROR",
                "message"    : "I had trouble fetching that data. Please try again.",
            },
        )
        result = node(state)

        text = result["turn"]["last_odoo_response"]["text"]
        assert "try again" in text.lower()
        mock_anthropic.return_value.messages.create.assert_not_called()

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_ambiguous_intent_returns_clarification(self, mock_anthropic):
        node  = make_node()
        state = make_state(
            intent_type   = IntentType.AMBIGUOUS,
            odoo_response = None,
        )
        result = node(state)

        text = result["turn"]["last_odoo_response"]["text"]
        assert "clarify" in text.lower() or "sure" in text.lower()
        mock_anthropic.return_value.messages.create.assert_not_called()

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_no_data_returns_not_found_message(self, mock_anthropic):
        node  = make_node()
        state = make_state(odoo_response=None)
        result = node(state)

        text = result["turn"]["last_odoo_response"]["text"]
        assert "could not find" in text.lower()
        mock_anthropic.return_value.messages.create.assert_not_called()

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_conversation_history_updated(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("Sales data retrieved successfully.")
        )
        node  = make_node()
        state = make_state(
            raw_input     = "Show me total sales",
            odoo_response = {"value": 5000},
        )
        initial_history_len = len(state.session.conversation_history)
        node(state)

        # Two turns appended: user + assistant
        assert len(state.session.conversation_history) == initial_history_len + 2
        assert state.session.conversation_history[-2].role == "user"
        assert state.session.conversation_history[-1].role == "assistant"

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_visualization_attached_to_response(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("Here is your KPI data.")
        )
        viz = {"visual_type": "KPI_CARD", "value": 5000}
        node  = make_node()
        state = make_state(
            odoo_response = {"value": 5000},
            visualization = viz,
        )
        result = node(state)

        assert result["turn"]["last_odoo_response"]["visualization"] == viz

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_unsupported_language_falls_back_to_english(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("Sales data retrieved.")
        )
        node  = make_node()
        state = make_state(language="fr", odoo_response={"value": 1000})
        result = node(state)

        assert result["turn"]["last_odoo_response"]["language"] == "en"

    @patch("core.nodes.response_formatter_node.anthropic.Anthropic")
    def test_returns_partial_dict_only(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_text("Response text.")
        )
        node   = make_node()
        state  = make_state(odoo_response={"value": 100})
        result = node(state)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"turn", "session"}

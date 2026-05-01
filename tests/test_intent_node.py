"""
OOA Phase 2 — Intent Classifier Tests
=======================================
File   : tests/test_intent_node.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from core.nodes.intent_node import IntentClassifierNode
from core.state import (
    AgentState,
    ErrorSeverity,
    IntentRecord,
    IntentType,
    OdooVersion,
    SessionState,
    TurnState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    raw_input     : str = "",
    active_domain : str | None = None,
    turn_number   : int = 1,
) -> AgentState:
    session = SessionState(
        odoo_user_id  = 1,
        odoo_version  = OdooVersion.V14,
        odoo_url      = "http://localhost:8069",
        active_domain = active_domain,
    )
    turn = TurnState(raw_input=raw_input, turn_number=turn_number)
    return AgentState(session=session, turn=turn)


def make_node(threshold: float = 0.75) -> IntentClassifierNode:
    return IntentClassifierNode(
        api_key              = "sk-ant-fake-test-key",
        confidence_threshold = threshold,
    )


def mock_claude(intent: str, confidence: float, domain: str) -> MagicMock:
    payload = json.dumps({
        "intent_type"     : intent,
        "confidence_score": confidence,
        "odoo_domain"     : domain,
        "reasoning"       : "Test classification.",
    })
    mock_content  = MagicMock()
    mock_content.text = payload
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIntentClassifierNode:

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_classifies_kpi_intent(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("KPI", 0.95, "sale.order")
        )
        node   = make_node()
        state  = make_state("What is our total sales this month?")
        result = node(state)

        assert result["turn"]["turn_intent"].intent_type == IntentType.KPI
        assert result["session"]["active_domain"] == "sale.order"

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_classifies_rag_intent(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("RAG", 0.92, "account.move")
        )
        node   = make_node()
        state  = make_state("Find the last invoice for Mr. Khan")
        result = node(state)

        assert result["turn"]["turn_intent"].intent_type == IntentType.RAG
        assert result["session"]["active_domain"] == "account.move"

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_classifies_write_intent(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("WRITE", 0.88, "sale.order")
        )
        node   = make_node()
        state  = make_state("Create a draft quote for Customer A")
        result = node(state)

        assert result["turn"]["turn_intent"].intent_type == IntentType.WRITE

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_low_confidence_forces_ambiguous(self, mock_anthropic):
        # Claude returns KPI but with low confidence
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("KPI", 0.50, "sale.order")
        )
        node   = make_node(threshold=0.75)
        state  = make_state("Something vague")
        result = node(state)

        # Must be forced to AMBIGUOUS despite Claude saying KPI
        assert result["turn"]["turn_intent"].intent_type == IntentType.AMBIGUOUS

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_sticky_domain_inherited_on_followup(self, mock_anthropic):
        # Claude returns unknown domain — should inherit from session
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("KPI", 0.85, "unknown")
        )
        node  = make_node()
        state = make_state(
            raw_input     = "And what about last month?",
            active_domain = "sale.order",
        )
        result = node(state)

        # Domain inherited from session
        assert result["session"]["active_domain"] == "sale.order"
        assert result["turn"]["turn_intent"].inherited is True

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_api_failure_returns_recoverable_error(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.side_effect = (
            Exception("API timeout")
        )
        node   = make_node()
        state  = make_state("Show me sales")
        result = node(state)

        assert result["turn"]["error_state"].severity == ErrorSeverity.RECOVERABLE
        assert result["turn"]["turn_intent"].intent_type == IntentType.AMBIGUOUS

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_empty_input_returns_ambiguous(self, mock_anthropic):
        node   = make_node()
        state  = make_state(raw_input="")
        result = node(state)

        mock_anthropic.return_value.messages.create.assert_not_called()
        assert result["turn"]["turn_intent"].intent_type == IntentType.AMBIGUOUS

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_intent_record_has_correct_turn_number(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("RAG", 0.90, "res.partner")
        )
        node   = make_node()
        state  = make_state("Find customer", turn_number=5)
        result = node(state)

        assert result["turn"]["turn_intent"].classified_at_turn == 5

    @patch("core.nodes.intent_node.anthropic.Anthropic")
    def test_returns_partial_dict_only(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude("KPI", 0.88, "sale.order")
        )
        node   = make_node()
        state  = make_state("Total revenue today")
        result = node(state)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"turn", "session"}

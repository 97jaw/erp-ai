"""
OOA Phase 2 — RAG Node Tests
==============================
File   : tests/test_rag_node.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from core.nodes.rag_node import RAGNode, SearchParams
from core.state import (
    AgentState,
    ErrorSeverity,
    OdooVersion,
    SessionState,
    TurnState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    raw_input     : str = "",
    active_domain : str = "sale.order",
    language      : str = "en",
) -> AgentState:
    session = SessionState(
        odoo_user_id  = 1,
        odoo_version  = OdooVersion.V14,
        odoo_url      = "http://localhost:8069",
        active_domain = active_domain,
        user_language = language,
    )
    turn = TurnState(raw_input=raw_input, turn_number=2)
    return AgentState(session=session, turn=turn)


def make_node() -> RAGNode:
    return RAGNode(api_key="sk-ant-fake-test-key")


def make_adapter(fields_valid: bool = True) -> MagicMock:
    """Creates a mock adapter."""
    adapter = MagicMock()
    adapter.field_exists.return_value = fields_valid
    adapter.search_read.return_value  = [
        {"id": 1, "name": "INV/2026/001", "amount_total": 5000.0},
        {"id": 2, "name": "INV/2026/002", "amount_total": 3200.0},
    ]
    return adapter


def mock_claude_extraction(
    model : str = "account.move",
    fields: list = None,
    domain: list = None,
    limit : int  = 10,
) -> MagicMock:
    payload = json.dumps({
        "model" : model,
        "domain": domain or [["partner_id.name", "ilike", "Khan"]],
        "fields": fields or ["name", "amount_total", "state"],
        "limit" : limit,
        "order" : "date desc",
    })
    mock_content      = MagicMock()
    mock_content.text = payload
    mock_response     = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRAGNode:

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_successful_retrieval(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        adapter = make_adapter(fields_valid=True)
        node    = make_node()
        state   = make_state("Find last invoices for Mr. Khan")
        result  = node(state, adapter)

        assert result["turn"]["last_odoo_response"] is not None
        assert len(result["turn"]["last_odoo_response"]) == 2
        assert result["turn"]["requires_discovery"] is False

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_invalid_fields_trigger_discovery(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        # Adapter says fields are invalid
        adapter = make_adapter(fields_valid=False)
        node    = make_node()
        state   = make_state("Find invoices")
        result  = node(state, adapter)

        assert result["turn"]["requires_discovery"] is True
        assert "last_odoo_response" not in result["turn"]

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_search_read_failure_returns_recoverable_error(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        adapter = make_adapter(fields_valid=True)
        adapter.search_read.side_effect = Exception("Odoo RPC timeout")
        node    = make_node()
        state   = make_state("Find invoices")
        result  = node(state, adapter)

        assert result["turn"]["error_state"] is not None
        assert result["turn"]["error_state"].severity == ErrorSeverity.RECOVERABLE

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_extraction_failure_returns_recoverable_error(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.side_effect = (
            Exception("API timeout")
        )
        adapter = make_adapter()
        node    = make_node()
        state   = make_state("Find invoices")
        result  = node(state, adapter)

        assert result["turn"]["error_state"].severity == ErrorSeverity.RECOVERABLE

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_adapter_search_read_called_with_correct_params(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction(
                model  = "account.move",
                fields = ["name", "amount_total"],
                domain = [["state", "=", "posted"]],
                limit  = 5,
            )
        )
        adapter = make_adapter(fields_valid=True)
        node    = make_node()
        state   = make_state("Show posted invoices")
        node(state, adapter)

        adapter.search_read.assert_called_once_with(
            model  = "account.move",
            domain = [("state", "=", "posted")],
            fields = ["name", "amount_total"],
            limit  = 5,
            order  = "date desc",
        )

    @patch("core.nodes.rag_node.anthropic.Anthropic")
    def test_returns_partial_dict_only(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        adapter = make_adapter(fields_valid=True)
        node    = make_node()
        state   = make_state("Find records")
        result  = node(state, adapter)

        assert isinstance(result, dict)
        assert "session" not in result
        assert "turn" in result

    def test_search_params_domain_to_tuples(self):
        """SearchParams.to_odoo_domain() must convert lists to tuples."""
        params = SearchParams(
            model  = "sale.order",
            domain = [["state", "=", "sale"], ["partner_id", "!=", False]],
            fields = ["name", "amount_total"],
            limit  = 10,
        )
        domain = params.to_odoo_domain()
        assert domain[0] == ("state", "=", "sale")
        assert domain[1] == ("partner_id", "!=", False)
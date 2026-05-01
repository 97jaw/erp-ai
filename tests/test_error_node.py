"""
OOA Phase 2 — Error Handler Node Tests
========================================
File   : tests/test_error_node.py
"""

import pytest
from core.nodes.error_node import ErrorHandlerNode
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    OdooVersion,
    SessionState,
    TurnState,
    ActiveFilters,
)
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    error        : ErrorState | None = None,
    language     : str = "en",
    active_domain: str = "sale.order",
) -> AgentState:
    session = SessionState(
        odoo_user_id  = 1,
        odoo_version  = OdooVersion.V14,
        odoo_url      = "http://localhost:8069",
        active_domain = active_domain,
        user_language = language,
        company_ids   = [1, 2],
    )
    turn = TurnState(
        raw_input      = "Show me sales",
        turn_number    = 3,
        input_language = language,
        error_state    = error,
    )
    return AgentState(session=session, turn=turn)


def make_recoverable_error() -> ErrorState:
    return ErrorState(
        severity    = ErrorSeverity.RECOVERABLE,
        source_node = "RAGNode",
        message     = "search_read failed: timeout",
    )


def make_fatal_error() -> ErrorState:
    return ErrorState(
        severity    = ErrorSeverity.FATAL,
        source_node = "SessionHydrationNode",
        message     = "Cannot connect to Postgres",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestErrorHandlerNode:

    def test_recoverable_error_english_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error(), language="en")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "try again" in payload["message"].lower()
        assert payload["recoverable"] is True
        assert payload["severity"] == "RECOVERABLE"

    def test_recoverable_error_arabic_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error(), language="ar")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "ar" in payload["message"] or "مشكلة" in payload["message"]
        assert payload["recoverable"] is True

    def test_recoverable_error_urdu_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error(), language="ur")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "ڈیٹا" in payload["message"]
        assert payload["recoverable"] is True

    def test_fatal_error_english_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_fatal_error(), language="en")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "support" in payload["message"].lower()
        assert payload["recoverable"] is False
        assert payload["severity"] == "FATAL"

    def test_fatal_error_arabic_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_fatal_error(), language="ar")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "الدعم" in payload["message"]

    def test_fatal_error_urdu_message(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_fatal_error(), language="ur")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "سپورٹ" in payload["message"]

    def test_session_state_never_modified(self):
        """Core guarantee — SessionState must be identical before and after."""
        node  = ErrorHandlerNode()
        state = make_state(error=make_recoverable_error(), language="en")

        # Capture session values before
        domain_before   = state.session.active_domain
        company_before  = state.session.company_ids
        language_before = state.session.user_language

        result = node(state)

        # Session must be untouched
        assert state.session.active_domain  == domain_before
        assert state.session.company_ids    == company_before
        assert state.session.user_language  == language_before
        assert "session" not in result

    def test_no_error_returns_empty_dict(self):
        """If called with no error, node returns empty dict gracefully."""
        node   = ErrorHandlerNode()
        state  = make_state(error=None)
        result = node(state)

        assert result == {}

    def test_unsupported_language_falls_back_to_english(self):
        """French or any unsupported language must fall back to English."""
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error(), language="fr")
        result = node(state)

        payload = result["turn"]["visualization_payload"]
        assert "try again" in payload["message"].lower()

    def test_returns_partial_dict_only(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error())
        result = node(state)

        assert isinstance(result, dict)
        assert "session" not in result
        assert "turn" in result

    def test_source_node_preserved_in_payload(self):
        node   = ErrorHandlerNode()
        state  = make_state(error=make_recoverable_error())
        result = node(state)

        assert result["turn"]["visualization_payload"]["source_node"] == "RAGNode"

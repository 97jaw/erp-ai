"""
OOA Phase 2 — Orchestrator Tests
==================================
File   : tests/test_orchestrator.py
"""

import pytest
from unittest.mock import MagicMock, patch

from core.orchestrator import route_by_intent, route_after_execution
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
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
    intent_type : IntentType | None = None,
    error       : ErrorState | None = None,
    discovery   : bool = False,
) -> AgentState:
    session = SessionState(
        odoo_user_id = 1,
        odoo_version = OdooVersion.V14,
        odoo_url     = "http://localhost:8069",
    )
    turn = TurnState(
        raw_input          = "test input",
        turn_number        = 1,
        error_state        = error,
        requires_discovery = discovery,
        turn_intent        = IntentRecord(
            intent_type        = intent_type,
            confidence_score   = 0.90,
            classified_at_turn = 1,
        ) if intent_type else None,
    )
    return AgentState(session=session, turn=turn)


# ---------------------------------------------------------------------------
# Routing Tests
# ---------------------------------------------------------------------------

class TestRouteByIntent:

    def test_rag_intent_routes_to_rag(self):
        state = make_state(intent_type=IntentType.RAG)
        assert route_by_intent(state) == "rag"

    def test_kpi_intent_routes_to_kpi(self):
        state = make_state(intent_type=IntentType.KPI)
        assert route_by_intent(state) == "kpi"

    def test_ambiguous_intent_routes_to_ambiguous(self):
        state = make_state(intent_type=IntentType.AMBIGUOUS)
        assert route_by_intent(state) == "ambiguous"

    def test_error_state_overrides_intent(self):
        """Even a valid intent must route to error if error_state is set."""
        error = ErrorState(
            severity    = ErrorSeverity.RECOVERABLE,
            source_node = "IntentClassifierNode",
            message     = "API timeout",
        )
        state = make_state(intent_type=IntentType.KPI, error=error)
        assert route_by_intent(state) == "error"

    def test_no_intent_routes_to_ambiguous(self):
        state = make_state(intent_type=None)
        assert route_by_intent(state) == "ambiguous"

    def test_unknown_intent_routes_to_ambiguous(self):
        state = make_state(intent_type=IntentType.UNKNOWN)
        assert route_by_intent(state) == "ambiguous"


class TestRouteAfterExecution:

    def test_clean_state_routes_to_format(self):
        state = make_state()
        assert route_after_execution(state) == "format"

    def test_error_state_routes_to_error(self):
        error = ErrorState(
            severity    = ErrorSeverity.RECOVERABLE,
            source_node = "RAGNode",
            message     = "search failed",
        )
        state = make_state(error=error)
        assert route_after_execution(state) == "error"

    def test_discovery_flag_routes_to_error(self):
        state = make_state(discovery=True)
        assert route_after_execution(state) == "error"

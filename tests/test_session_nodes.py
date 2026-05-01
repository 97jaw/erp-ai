"""
OOA Phase 2 — Node Tests
=========================
File   : tests/test_session_nodes.py
"""

import pytest
from core.nodes.session_nodes import SessionHydrationNode, TurnResetNode
from core.session_store import InMemorySessionStore
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    IntentType,
    OdooVersion,
    SessionState,
    TurnState,
)


def make_agent_state(session_id: str = "test-session-001") -> AgentState:
    session = SessionState(
        session_id   = session_id,
        odoo_user_id = 1,
        odoo_version = OdooVersion.V14,
        odoo_url     = "http://localhost:8069",
        company_ids  = [1],
    )
    turn = TurnState(raw_input="What is our total sales today?")
    return AgentState(session=session, turn=turn)


class TestSessionHydrationNode:

    def test_new_session_is_saved_and_returned(self):
        store = InMemorySessionStore()
        node  = SessionHydrationNode(store=store)
        state = make_agent_state("new-session-001")
        result = node(state)
        assert "session" in result
        assert result["session"].session_id == "new-session-001"
        assert store.load("new-session-001") is not None

    def test_existing_session_is_loaded(self):
        store = InMemorySessionStore()
        node  = SessionHydrationNode(store=store)
        state = make_agent_state("existing-session-001")
        node(state)
        stored = store.load("existing-session-001")
        stored.append_turn("user", "previous message")
        store.save("existing-session-001", stored)
        result = node(state)
        assert len(result["session"].conversation_history) == 1

    def test_failed_load_returns_recoverable_error(self):
        class BrokenStore(InMemorySessionStore):
            def load(self, session_id):
                raise ConnectionError("Postgres is down")
        node   = SessionHydrationNode(store=BrokenStore())
        state  = make_agent_state("broken-session-001")
        result = node(state)
        assert "turn" in result
        assert result["turn"].error_state.severity == ErrorSeverity.RECOVERABLE

    def test_returns_partial_dict_not_full_state(self):
        store  = InMemorySessionStore()
        node   = SessionHydrationNode(store=store)
        state  = make_agent_state()
        result = node(state)
        assert isinstance(result, dict)
        assert list(result.keys()) == ["session"]


class TestTurnResetNode:

    def test_turn_is_fully_reset(self):
        state = make_agent_state()
        state.turn.extracted_params   = {"date": "2026-01-01"}
        state.turn.last_odoo_response = {"records": [1, 2, 3]}
        state.turn.error_state        = ErrorState(
            severity=ErrorSeverity.RECOVERABLE,
            source_node="KPINode",
            message="old error"
        )
        state.turn.raw_input = "New question this turn"
        node   = TurnResetNode()
        result = node(state)
        assert result["turn"].extracted_params   == {}
        assert result["turn"].last_odoo_response is None
        assert result["turn"].error_state        is None

    def test_raw_input_is_preserved(self):
        state = make_agent_state()
        state.turn.raw_input = "Show me inventory for Karachi warehouse"
        result = TurnResetNode()(state)
        assert result["turn"].raw_input == "Show me inventory for Karachi warehouse"

    def test_turn_counter_increments(self):
        state = make_agent_state()
        state.turn.turn_number = 4
        result = TurnResetNode()(state)
        assert result["turn"].turn_number == 5

    def test_session_is_not_touched(self):
        state  = make_agent_state()
        result = TurnResetNode()(state)
        assert "session" not in result
        assert list(result.keys()) == ["turn"]

    def test_turn_counter_starts_at_one(self):
        state  = make_agent_state()
        result = TurnResetNode()(state)
        assert result["turn"].turn_number == 1

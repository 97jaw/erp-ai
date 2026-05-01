"""
Tests: AgentState Contract
==========================
File   : tests/test_state.py
Status : STUB — add test cases as nodes are implemented.
"""

import pytest
from core.state import (
    AgentState, SessionState, TurnState,
    IntentRecord, IntentType, OdooVersion,
    ActiveFilters,
)


def make_session() -> SessionState:
    return SessionState(
        odoo_user_id=1,
        odoo_version=OdooVersion.V14,
        odoo_url="http://localhost:8069",
    )


def test_agent_state_creates_fresh_turn():
    session = make_session()
    state = AgentState(session=session)
    assert state.turn.raw_input == ""
    assert state.turn.error_state is None


def test_session_append_turn_prunes_history():
    session = make_session()
    session.max_history_turns = 3
    for i in range(5):
        session.append_turn("user", f"message {i}")
    assert len(session.conversation_history) == 3


def test_patch_filters_preserves_company():
    from datetime import datetime
    session = make_session()
    session.active_filters.company_ids = [1, 2]
    session.patch_filters(date_from=datetime(2026, 1, 1))
    assert session.active_filters.company_ids == [1, 2]
    assert session.active_filters.date_from == datetime(2026, 1, 1)


def test_inherit_intent_sets_flag():
    session = make_session()
    session.active_intent = IntentRecord(
        intent_type=IntentType.KPI,
        confidence_score=0.95,
        classified_at_turn=1,
        inherited=False,
    )
    inherited = session.inherit_intent(current_turn=2)
    assert inherited.inherited is True
    assert inherited.classified_at_turn == 2

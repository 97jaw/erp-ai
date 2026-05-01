"""
OOA Phase 2 — Node 1 & 2
=========================
File    : core/nodes/session_nodes.py
Author  : Lead Backend Developer
Version : 1.0.0

Contains:
    - SessionHydrationNode  : Loads or creates SessionState from Postgres
    - TurnResetNode         : Resets TurnState at the start of every turn

Architecture (Both Suggestions Approved):
    - Nodes are CLASSES with __call__ for dependency injection
    - Nodes return PARTIAL DICTS (only mutated fields) not full AgentState
"""

from __future__ import annotations

import logging
from typing import Any

from core.session_store import PostgresSessionStore, SessionStore
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    SessionState,
    TurnState,
)

logger = logging.getLogger(__name__)


class SessionHydrationNode:
    """
    FIRST NODE in the graph. Runs before anything else.

    Responsibilities:
        1. Accept raw input (text or voice transcript) + session_id
        2. Try to load existing SessionState from Postgres
        3. If no session found → create a fresh SessionState
        4. Return ONLY the session key (partial dict pattern)
    """

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def __call__(self, state: AgentState) -> dict[str, Any]:
        session_id = state.session.session_id

        try:
            existing = self.store.load(session_id)

            if existing:
                logger.info(
                    "[SessionHydration] Loaded existing session %s "
                    "(user=%s, version=%s, turns=%d)",
                    session_id,
                    existing.odoo_user_id,
                    existing.odoo_version,
                    len(existing.conversation_history),
                )
                return {"session": existing}

            logger.info(
                "[SessionHydration] New session %s for user %s",
                session_id,
                state.session.odoo_user_id,
            )
            self.store.save(session_id, state.session)
            return {"session": state.session}

        except Exception as exc:
            logger.error(
                "[SessionHydration] Failed to load session %s: %s",
                session_id, exc
            )
            error = ErrorState(
                severity    = ErrorSeverity.RECOVERABLE,
                source_node = "SessionHydrationNode",
                message     = f"Session load failed, starting fresh: {exc}",
            )
            fresh_turn = TurnState(error_state=error)
            return {"turn": fresh_turn}


class TurnResetNode:
    """
    SECOND NODE in the graph. Runs immediately after SessionHydrationNode.

    Responsibilities:
        1. Wipe all ephemeral TurnState fields from the previous turn
        2. Inject the raw user input into the fresh TurnState
        3. Increment the turn counter
        4. Return ONLY the turn key (partial dict pattern)
    """

    def __call__(self, state: AgentState) -> dict[str, Any]:
        raw_input            = state.turn.raw_input
        previous_turn_number = state.turn.turn_number

        fresh_turn = TurnState(
            raw_input   = raw_input,
            turn_number = previous_turn_number + 1,
        )

        logger.info(
            "[TurnReset] Session %s — starting turn %d | input: '%s'",
            state.session.session_id,
            fresh_turn.turn_number,
            raw_input[:60] + "..." if len(raw_input) > 60 else raw_input,
        )

        return {"turn": fresh_turn}

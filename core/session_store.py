"""
OOA Session Store
=================
File    : core/session_store.py
Status  : STUB — Phase 2

Implements the abstract SessionStore interface and two concrete backends:
    - InMemorySessionStore  : Local development and testing
    - PostgresSessionStore  : Production (LangGraph checkpointer)

Both expose:
    load(session_id: str) -> SessionState
    save(session_id: str, state: SessionState) -> None
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from core.state import SessionState

load_dotenv()
logger = logging.getLogger(__name__)
from core.state import SessionState


class SessionStore(ABC):
    @abstractmethod
    def load(self, session_id: str) -> SessionState:
        ...

    @abstractmethod
    def save(self, session_id: str, state: SessionState) -> None:
        ...


class InMemorySessionStore(SessionStore):
    """Development only. Data lost on restart."""

    def __init__(self) -> None:
        self._store: dict[str, SessionState] = {}
        logger.warning(
            "[SessionStore] Using InMemorySessionStore — "
            "data will NOT persist across restarts."
        )

    def load(self, session_id: str) -> Optional[SessionState]:
        return self._store.get(session_id)

    def save(self, session_id: str, state: SessionState) -> None:
        self._store[session_id] = state

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

class PostgresSessionStore(SessionStore):
    """Production backend. Uses LangGraph Postgres checkpointer."""

    def load(self, session_id: str) -> SessionState:
        raise NotImplementedError("Implement in Phase 2.")

    def save(self, session_id: str, state: SessionState) -> None:
        raise NotImplementedError("Implement in Phase 2.")

"""
OOA Phase 2 — Session Store
============================
File    : core/session_store.py
Author  : Lead Backend Developer
Version : 1.0.0

Implements:
    SessionStore          : Abstract base (interface contract)
    InMemorySessionStore  : Development fallback
    PostgresSessionStore  : Production backend (approved directive)

Table schema (auto-created on first run):
    CREATE TABLE ooa_sessions (
        session_id   TEXT PRIMARY KEY,
        state_json   JSONB NOT NULL,
        created_at   TIMESTAMPTZ DEFAULT now(),
        updated_at   TIMESTAMPTZ DEFAULT now()
    );
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


class SessionStore(ABC):

    @abstractmethod
    def load(self, session_id: str) -> Optional[SessionState]:
        ...

    @abstractmethod
    def save(self, session_id: str, state: SessionState) -> None:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...


class InMemorySessionStore(SessionStore):
    """Development store — persists within server process lifetime."""

    _global_store: dict[str, SessionState] = {}  # Class-level persistence

    def __init__(self) -> None:
        logger.warning(
            "[SessionStore] Using InMemorySessionStore — "
            "data persists within server process only."
        )

    def load(self, session_id: str) -> Optional[SessionState]:
        return InMemorySessionStore._global_store.get(session_id)

    def save(self, session_id: str, state: SessionState) -> None:
        InMemorySessionStore._global_store[session_id] = state

    def delete(self, session_id: str) -> None:
        InMemorySessionStore._global_store.pop(session_id, None)

class PostgresSessionStore(SessionStore):
    """
    Persists SessionState as JSONB in Postgres.
    Connection read from POSTGRES_DSN in .env file.
    Auto-creates the ooa_sessions table on first run.
    """

    TABLE = "ooa_sessions"

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.environ.get("POSTGRES_DSN")
        if not self.dsn:
            raise ValueError(
                "POSTGRES_DSN environment variable is required. "
                "Add it to your .env file."
            )
        self._conn = None
        self._ensure_connection()
        self._ensure_table()

    def load(self, session_id: str) -> Optional[SessionState]:
        self._ensure_connection()
        try:
            with self._conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(
                    f"SELECT state_json FROM {self.TABLE} "
                    f"WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()

            if row is None:
                return None

            return SessionState(**row["state_json"])

        except Exception as exc:
            logger.error("[Postgres] Load failed for %s: %s", session_id, exc)
            self._conn.rollback()
            raise

    def save(self, session_id: str, state: SessionState) -> None:
        self._ensure_connection()
        try:
            state_json = json.dumps(
                state.model_dump(mode="json"), default=str
            )
            with self._conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.TABLE}
                        (session_id, state_json, created_at, updated_at)
                    VALUES (%s, %s::jsonb, now(), now())
                    ON CONFLICT (session_id) DO UPDATE
                        SET state_json = EXCLUDED.state_json,
                            updated_at = now()
                    """,
                    (session_id, state_json),
                )
            self._conn.commit()

        except Exception as exc:
            logger.error("[Postgres] Save failed for %s: %s", session_id, exc)
            self._conn.rollback()
            raise

    def delete(self, session_id: str) -> None:
        self._ensure_connection()
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.TABLE} WHERE session_id = %s",
                    (session_id,),
                )
            self._conn.commit()

        except Exception as exc:
            logger.error("[Postgres] Delete failed for %s: %s", session_id, exc)
            self._conn.rollback()
            raise

    def _ensure_connection(self) -> None:
        try:
            if self._conn is None or self._conn.closed:
                self._conn = psycopg2.connect(self.dsn)
                logger.info("[Postgres] Connection established.")
        except psycopg2.OperationalError as exc:
            logger.error("[Postgres] Cannot connect: %s", exc)
            raise

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    session_id   TEXT PRIMARY KEY,
                    state_json   JSONB        NOT NULL,
                    created_at   TIMESTAMPTZ  DEFAULT now(),
                    updated_at   TIMESTAMPTZ  DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS idx_ooa_sessions_updated
                    ON {self.TABLE} (updated_at DESC);
                """
            )
        self._conn.commit()
        logger.info("[Postgres] Table '%s' is ready.", self.TABLE)

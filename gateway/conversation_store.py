from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID

from admin.auth.config import auth_db_enabled
from admin.db.connection import init_admin_db
from admin.db.repositories.conversations import ConversationRepository

logger = logging.getLogger(__name__)

_AGENT_MESSAGE_LIMIT = 20


class ConversationStore:
    """
    Chat history store.

    Priority:
    1. OOA_DB_URL — admin `conversations` / `messages` (user-scoped, Phase 4)
    2. POSTGRES_DSN — legacy `ooa_conversations` JSON blob
    3. In-memory fallback
    """

    _memory: dict[str, list] = {}
    _use_legacy_pg = bool(os.environ.get("POSTGRES_DSN")) and not auth_db_enabled()
    _pg_table_ready = False
    _conversation_ids: dict[str, str] = {}

    @classmethod
    def _use_admin_db(cls) -> bool:
        return auth_db_enabled()

    @classmethod
    async def _repo(cls) -> ConversationRepository:
        db = await init_admin_db()
        return ConversationRepository(db)

    @classmethod
    def conversation_id_for_session(cls, session_id: str) -> str | None:
        return cls._conversation_ids.get(session_id)

    @classmethod
    async def get(
        cls,
        session_id: str,
        *,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if cls._use_admin_db() and user_id is not None:
            repo = await cls._repo()
            conv_id = await repo.get_or_create(user_id, session_id)
            cls._conversation_ids[session_id] = str(conv_id)
            return await repo.get_agent_messages(conv_id, limit=_AGENT_MESSAGE_LIMIT)
        return cls._legacy_get(session_id)

    @classmethod
    async def append(
        cls,
        session_id: str,
        role: str,
        content: Any,
        *,
        user_id: int | None = None,
        language: str | None = None,
        visualization: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        response_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if cls._use_admin_db() and user_id is not None:
            repo = await cls._repo()
            conv_id = await repo.get_or_create(user_id, session_id)
            cls._conversation_ids[session_id] = str(conv_id)
            await repo.append_message(
                conv_id,
                user_id=user_id if role == "user" else None,
                role=role,
                content=content,
                language=language,
                visualization=visualization,
                suggestions=suggestions,
                response_time_ms=response_time_ms,
            )
            return await repo.get_agent_messages(conv_id, limit=_AGENT_MESSAGE_LIMIT)

        messages = cls._legacy_get(session_id)
        messages.append({"role": role, "content": content})
        if len(messages) > _AGENT_MESSAGE_LIMIT:
            messages = messages[-_AGENT_MESSAGE_LIMIT:]
        cls._legacy_save(session_id, messages)
        return messages

    @classmethod
    async def clear(
        cls,
        session_id: str,
        *,
        user_id: int | None = None,
    ) -> None:
        if cls._use_admin_db() and user_id is not None:
            repo = await cls._repo()
            conv_id = await repo.resolve_id(user_id, session_id)
            if conv_id:
                await repo.delete_conversation(user_id, conv_id)
            cls._conversation_ids.pop(session_id, None)
            return
        cls._legacy_clear(session_id)

    @classmethod
    def _legacy_get(cls, session_id: str) -> list:
        if session_id in cls._memory:
            return list(cls._memory[session_id])
        if cls._use_legacy_pg:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT messages FROM ooa_conversations WHERE session_id = %s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                conn.close()
                messages = row[0] if row else []
                cls._memory[session_id] = list(messages)
                return list(messages)
            except Exception as exc:
                logger.error("[ConversationStore] PG get failed: %s", exc)
        return []

    @classmethod
    def _legacy_save(cls, session_id: str, messages: list) -> None:
        cls._memory[session_id] = list(messages)
        if cls._use_legacy_pg:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ooa_conversations (session_id, messages, updated_at)
                        VALUES (%s, %s::jsonb, now())
                        ON CONFLICT (session_id) DO UPDATE
                        SET messages = EXCLUDED.messages, updated_at = now()
                        """,
                        (session_id, json.dumps(messages, default=str)),
                    )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.error("[ConversationStore] PG save failed: %s", exc)

    @classmethod
    def _legacy_clear(cls, session_id: str) -> None:
        if cls._use_legacy_pg:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM ooa_conversations WHERE session_id = %s",
                        (session_id,),
                    )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.error("[ConversationStore] PG clear failed: %s", exc)
        cls._memory.pop(session_id, None)

    @classmethod
    def _ensure_table(cls, conn) -> None:
        if cls._pg_table_ready:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ooa_conversations (
                    session_id  TEXT PRIMARY KEY,
                    messages    JSONB NOT NULL DEFAULT '[]',
                    updated_at  TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        conn.commit()
        cls._pg_table_ready = True

    @classmethod
    def _get_pg_connection(cls):
        import psycopg2

        conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
        cls._ensure_table(conn)
        return conn

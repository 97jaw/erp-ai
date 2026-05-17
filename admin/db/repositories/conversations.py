from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import asyncpg

from admin.db.connection import AdminDatabase

_AGENT_MESSAGE_LIMIT = 20
_TITLE_MAX = 120


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content)


def _title_from_message(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= _TITLE_MAX:
        return cleaned
    return cleaned[: _TITLE_MAX - 1] + "…"


class ConversationRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def get_or_create(
        self,
        user_id: int,
        external_session_key: str,
        *,
        title: str | None = None,
    ) -> UUID:
        existing = await self._db.fetchval(
            """
            SELECT id FROM conversations
            WHERE user_id = $1 AND external_session_key = $2
            """,
            user_id,
            external_session_key,
        )
        if existing:
            return UUID(str(existing))
        return UUID(
            str(
                await self._db.fetchval(
                    """
                    INSERT INTO conversations (
                        user_id, external_session_key, title, metadata
                    )
                    VALUES ($1, $2, $3, $4::jsonb)
                    RETURNING id
                    """,
                    user_id,
                    external_session_key,
                    title,
                    json.dumps({"source": "ooa_chat"}),
                )
            )
        )

    async def resolve_id(
        self,
        user_id: int,
        session_key: str,
    ) -> UUID | None:
        row = await self._db.fetchval(
            """
            SELECT id FROM conversations
            WHERE user_id = $1
              AND (id::text = $2 OR external_session_key = $2)
            LIMIT 1
            """,
            user_id,
            session_key,
        )
        return UUID(str(row)) if row else None

    async def append_message(
        self,
        conversation_id: UUID,
        *,
        user_id: int | None,
        role: str,
        content: Any,
        language: str | None = None,
        visualization: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        tool_calls: Any = None,
        tokens_used: int | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        text = _content_to_text(content)
        await self._db.execute(
            """
            INSERT INTO messages (
                conversation_id, user_id, role, content, language,
                tool_calls, visualization, suggestions,
                tokens_used, response_time_ms
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10)
            """,
            conversation_id,
            user_id,
            role,
            text,
            language,
            json.dumps(tool_calls) if tool_calls is not None else None,
            json.dumps(visualization) if visualization is not None else None,
            suggestions,
            tokens_used,
            response_time_ms,
        )
        await self._db.execute(
            """
            UPDATE conversations
            SET last_message_at = NOW(),
                message_count = message_count + 1
            WHERE id = $1
            """,
            conversation_id,
        )
        if role == "user" and text.strip():
            await self._db.execute(
                """
                UPDATE conversations
                SET title = COALESCE(NULLIF(title, ''), $2)
                WHERE id = $1 AND (title IS NULL OR title = '')
                """,
                conversation_id,
                _title_from_message(text),
            )

    async def get_agent_messages(self, conversation_id: UUID, *, limit: int = _AGENT_MESSAGE_LIMIT) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            """
            SELECT role, content
            FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            ) recent
            ORDER BY created_at ASC
            """,
            conversation_id,
            limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def get_recent_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, role, content, language, visualization, suggestions,
                   created_at, tokens_used, response_time_ms
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            conversation_id,
            limit,
            offset,
        )

    async def list_for_user(
        self,
        user_id: int,
        *,
        search: str | None = None,
        include_archived: bool = False,
        limit: int = 30,
        offset: int = 0,
    ) -> list[asyncpg.Record]:
        if search:
            pattern = f"%{search}%"
            return await self._db.fetch(
                """
                SELECT c.id, c.title, c.started_at, c.last_message_at,
                       c.message_count, c.is_pinned, c.is_archived, c.external_session_key
                FROM conversations c
                WHERE c.user_id = $1
                  AND ($2 OR c.is_archived = FALSE)
                  AND (
                    c.title ILIKE $3
                    OR EXISTS (
                        SELECT 1 FROM messages m
                        WHERE m.conversation_id = c.id AND m.content ILIKE $3
                    )
                  )
                ORDER BY c.is_pinned DESC, c.last_message_at DESC
                LIMIT $4 OFFSET $5
                """,
                user_id,
                include_archived,
                pattern,
                limit,
                offset,
            )
        return await self._db.fetch(
            """
            SELECT id, title, started_at, last_message_at, message_count,
                   is_pinned, is_archived, external_session_key
            FROM conversations
            WHERE user_id = $1 AND ($2 OR is_archived = FALSE)
            ORDER BY is_pinned DESC, last_message_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            include_archived,
            limit,
            offset,
        )

    async def get_conversation(
        self,
        user_id: int,
        conversation_id: UUID,
    ) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT *
            FROM conversations
            WHERE id = $1 AND user_id = $2
            """,
            conversation_id,
            user_id,
        )

    async def delete_conversation(self, user_id: int, conversation_id: UUID) -> bool:
        result = await self._db.execute(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id,
            user_id,
        )
        return result.endswith("1")

    async def set_archived(
        self,
        user_id: int,
        conversation_id: UUID,
        *,
        archived: bool,
    ) -> bool:
        result = await self._db.execute(
            """
            UPDATE conversations
            SET is_archived = $3
            WHERE id = $1 AND user_id = $2
            """,
            conversation_id,
            user_id,
            archived,
        )
        return result.endswith("1")

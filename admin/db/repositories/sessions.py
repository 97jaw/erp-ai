from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from admin.db.connection import AdminDatabase
from admin.security.session_policy import is_session_idle_expired


class SessionRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        refresh_token_hash: str | None,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UUID:
        session_id = await self._db.fetchval(
            """
            INSERT INTO sessions (
                user_id, token_hash, refresh_token, ip_address, user_agent, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id,
            token_hash,
            refresh_token_hash,
            ip_address,
            user_agent,
            expires_at,
        )
        return session_id

    async def get_active_by_token_hash(self, token_hash: str) -> asyncpg.Record | None:
        row = await self._db.fetchrow(
            """
            SELECT s.*, u.file_id, u.name, u.language, u.is_active, u.is_super_admin
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = $1
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
              AND u.deleted_at IS NULL
            """,
            token_hash,
        )
        if row and is_session_idle_expired(row["last_activity"]):
            await self.revoke(token_hash, reason="idle_timeout")
            return None
        return row

    async def touch(self, session_id: UUID) -> None:
        await self._db.execute(
            "UPDATE sessions SET last_activity = NOW() WHERE id = $1",
            session_id,
        )

    async def revoke(self, token_hash: str, *, reason: str = "logout") -> None:
        await self._db.execute(
            """
            UPDATE sessions
            SET revoked_at = NOW(), revoked_reason = $2
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            token_hash,
            reason,
        )

    async def list_for_user(self, user_id: int) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, ip_address, user_agent, started_at, expires_at,
                   last_activity, revoked_at
            FROM sessions
            WHERE user_id = $1
            ORDER BY started_at DESC
            LIMIT 50
            """,
            user_id,
        )

    async def revoke_all_for_user(self, user_id: int, *, reason: str = "admin_revoke") -> int:
        result = await self._db.execute(
            """
            UPDATE sessions
            SET revoked_at = NOW(), revoked_reason = $2
            WHERE user_id = $1 AND revoked_at IS NULL
            """,
            user_id,
            reason,
        )
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def revoke_by_refresh_hash(self, refresh_hash: str, *, reason: str = "refresh") -> None:
        await self._db.execute(
            """
            UPDATE sessions
            SET revoked_at = NOW(), revoked_reason = $2
            WHERE refresh_token = $1 AND revoked_at IS NULL
            """,
            refresh_hash,
            reason,
        )

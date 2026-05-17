from __future__ import annotations

import json
from typing import Any

import asyncpg

from admin.db.connection import AdminDatabase


class FeatureFlagRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def list_all(self) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, code, name, description, is_enabled, rollout_percent,
                   enabled_roles, enabled_users, metadata, created_at, updated_at
            FROM feature_flags
            ORDER BY code
            """
        )

    async def get_by_id(self, flag_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM feature_flags WHERE id = $1",
            flag_id,
        )

    async def get_by_code(self, code: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM feature_flags WHERE code = $1",
            code,
        )

    async def create(
        self,
        *,
        code: str,
        name: str,
        description: str | None = None,
        is_enabled: bool = True,
        rollout_percent: int = 100,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return int(
            await self._db.fetchval(
                """
                INSERT INTO feature_flags (code, name, description, is_enabled, rollout_percent, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING id
                """,
                code,
                name,
                description,
                is_enabled,
                rollout_percent,
                json.dumps(metadata or {}),
            )
        )

    async def update(
        self,
        flag_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool | None = None,
        rollout_percent: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        row = await self.get_by_id(flag_id)
        if not row:
            return False
        await self._db.execute(
            """
            UPDATE feature_flags
            SET name = COALESCE($2, name),
                description = COALESCE($3, description),
                is_enabled = COALESCE($4, is_enabled),
                rollout_percent = COALESCE($5, rollout_percent),
                metadata = COALESCE($6::jsonb, metadata),
                updated_at = NOW()
            WHERE id = $1
            """,
            flag_id,
            name,
            description,
            is_enabled,
            rollout_percent,
            json.dumps(metadata) if metadata is not None else None,
        )
        return True

    async def delete(self, flag_id: int) -> bool:
        result = await self._db.execute(
            "DELETE FROM feature_flags WHERE id = $1",
            flag_id,
        )
        return result.endswith("1")

    async def enable_for_role(self, flag_id: int, role_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE feature_flags
            SET enabled_roles = array_append(COALESCE(enabled_roles, '{}'), $2),
                updated_at = NOW()
            WHERE id = $1
              AND NOT ($2 = ANY(COALESCE(enabled_roles, '{}')))
            """,
            flag_id,
            role_id,
        )
        return "UPDATE" in result

    async def enable_for_user(self, flag_id: int, user_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE feature_flags
            SET enabled_users = array_append(COALESCE(enabled_users, '{}'), $2),
                updated_at = NOW()
            WHERE id = $1
              AND NOT ($2 = ANY(COALESCE(enabled_users, '{}')))
            """,
            flag_id,
            user_id,
        )
        return "UPDATE" in result

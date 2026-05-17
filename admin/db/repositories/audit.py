from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from admin.db.connection import AdminDatabase


class AuditRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def log(
        self,
        *,
        user_id: int | None,
        event_type: str,
        event_action: str,
        status: str,
        session_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO audit_logs (
                user_id, session_id, event_type, event_action,
                resource_type, resource_id, ip_address, user_agent,
                status, error_message, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
            """,
            user_id,
            session_id,
            event_type,
            event_action,
            resource_type,
            resource_id,
            ip_address,
            user_agent,
            status,
            error_message,
            json.dumps(metadata or {}),
        )

    async def list_events(
        self,
        *,
        user_id: int | None = None,
        event_type: str | None = None,
        status: str | None = None,
        date_from: Any | None = None,
        date_to: Any | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[asyncpg.Record]:
        clauses = ["1=1"]
        args: list[Any] = []
        idx = 1
        if user_id is not None:
            clauses.append(f"user_id = ${idx}")
            args.append(user_id)
            idx += 1
        if event_type:
            clauses.append(f"event_type = ${idx}")
            args.append(event_type)
            idx += 1
        if status:
            clauses.append(f"status = ${idx}")
            args.append(status)
            idx += 1
        if date_from is not None:
            clauses.append(f"created_at >= ${idx}")
            args.append(date_from)
            idx += 1
        if date_to is not None:
            clauses.append(f"created_at < ${idx}")
            args.append(date_to)
            idx += 1
        args.extend([limit, offset])
        where = " AND ".join(clauses)
        return await self._db.fetch(
            f"""
            SELECT id, user_id, event_type, event_action, resource_type, resource_id,
                   status, ip_address, created_at, metadata
            FROM audit_logs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *args,
        )

    async def export_events(
        self,
        *,
        user_id: int | None = None,
        event_type: str | None = None,
        status: str | None = None,
        date_from: Any | None = None,
        date_to: Any | None = None,
        limit: int = 5000,
    ) -> list[asyncpg.Record]:
        return await self.list_events(
            user_id=user_id,
            event_type=event_type,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=min(limit, 10000),
            offset=0,
        )

    async def get_event(self, event_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM audit_logs WHERE id = $1",
            event_id,
        )
